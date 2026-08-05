"use client";

import { useEffect, useMemo, useRef } from "react";
import { Center, Resize, useAnimations, useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { SkeletonUtils } from "three-stdlib";

import { thwip } from "@/lib/sfx";

/** Renders a rigged humanoid from a glTF file, shaded to match the page.
 *
 *  Deliberately model-agnostic: it takes whatever skinned mesh is at `url`,
 *  finds the animation clip whose name looks closest to what it wants, and
 *  falls back to a procedural sway if the file ships no clips at all. That is
 *  the difference between a component tied to one asset and one you can drop a
 *  different character into without touching the code.
 *
 *  The imported materials are replaced rather than used. A model authored for
 *  physically based rendering arrives with roughness and metalness maps that
 *  look photographic, and a photographic figure is the one thing on this site
 *  that is not printed — so everything is re-shaded onto a toon ramp with an
 *  inverted-hull outline, and only the base colour survives the transfer.
 */

const INK = "#0b0b0f";
const UP = new THREE.Vector3(0, 1, 0);

/** Clip names vary by author. Prefer something idle-ish, take anything if not. */
const CLIP_PREFERENCE = [/idle/i, /hang/i, /float/i, /breath/i, /stand/i];

function toonRamp() {
  const steps = new Uint8Array([88, 148, 204, 255]);
  const ramp = new THREE.DataTexture(steps, steps.length, 1, THREE.RedFormat);
  ramp.minFilter = THREE.NearestFilter;
  ramp.magFilter = THREE.NearestFilter;
  ramp.generateMipmaps = false;
  ramp.needsUpdate = true;
  return ramp;
}

export function SlingerModel({
  url,
  scale = 1,
  outline = true,
  shootEvery = 6.4,
  suit = null,
  suitSplit = 0.52,
  targetHeight = 3,
  outlineWidth = 0.004,
  pose = [0, 0, 0],
  hideBelowVerts = 0,
  handBone = "DEF-hand.R",
  webTarget = [-2.6, 2.2, 0.4],
}: {
  url: string;
  scale?: number;
  outline?: boolean;
  shootEvery?: number;
  /** Two-tone suit. Pass null to keep the model's own materials. */
  suit?: { top: string; bottom: string } | null;
  /** Height of the colour break, 0 at the feet and 1 at the crown. */
  suitSplit?: number;
  /** World height the model is normalised to, whatever it was exported at. */
  targetHeight?: number;
  /** Ink line weight, as a fraction of view depth. */
  outlineWidth?: number;
  /** Resting rotation. A static sculpt has only its attitude to act with. */
  pose?: [number, number, number];
  /** Drop meshes below this vertex count. Character models routinely ship rig
   *  widgets and prop geometry that are not the character. */
  hideBelowVerts?: number;
  /** Which bone the web leaves from, by name.
   *
   *  Two traps here, both of which cost a debugging pass. Matching loosely on
   *  "hand" hits MCH-hand_ik_root long before the hand itself, and the strand
   *  then leaves from somewhere near the hips — the deform bone is the one at
   *  the end of the arm. And glTF import sanitises node names, so the file's
   *  `DEF-hand.R_rig` arrives as `DEF-hand_R_rig`: an exact or dot-sensitive
   *  match silently finds nothing and the web fires from the model's origin. */
  handBone?: string;
  /** Where the strand lands, in the figure's own space. */
  webTarget?: [number, number, number];
}) {
  const stage = useRef<THREE.Group>(null);
  const group = useRef<THREE.Group>(null);
  const strand = useRef<THREE.Mesh>(null);
  const splat = useRef<THREE.Mesh>(null);
  const fired = useRef(false);
  const scratch = useMemo(() => ({ from: new THREE.Vector3(), dir: new THREE.Vector3() }), []);
  const { scene, animations } = useGLTF(url);

  // Skinned meshes cannot be shared between renderers by reference — cloning
  // the scene graph normally leaves both copies driven by one skeleton.
  const model = useMemo(() => SkeletonUtils.clone(scene) as THREE.Group, [scene]);
  const ramp = useMemo(toonRamp, []);

  /* Framing is delegated to drei's Resize and Center rather than a bounding
     box computed here. Authors export at wildly different scales, origins and
     up-axes — this model is Z-up out of Blender with two extra meshes taller
     than the character — and a box measured from geometry in the bind pose
     gets all three wrong for a skinned mesh. Resize and Center measure what is
     actually in the scene, after transforms. */

  useEffect(() => {
    const outlines: THREE.Mesh[] = [];

    // Collect first. Adding the outline hull inside the traversal makes the
    // walk visit the hull it just created, clone that, and recurse until the
    // stack gives out.
    const meshes: THREE.Mesh[] = [];
    model.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) meshes.push(child as THREE.Mesh);
    });

    // Rig widgets and prop geometry come along with a lot of published models —
    // this one carries two meshes taller than the character itself, which
    // render as grey slabs once the original materials are replaced.
    if (hideBelowVerts > 0) {
      meshes.forEach((mesh) => {
        const count = mesh.geometry?.getAttribute("position")?.count ?? 0;
        if (count < hideBelowVerts) mesh.visible = false;
      });
    }

    // Where the trunks start, in the model's own bind pose.
    const bounds = new THREE.Box3().setFromObject(model);
    const height = Math.max(bounds.max.y - bounds.min.y, 1e-4);
    const split = bounds.min.y + height * suitSplit;
    // Proportional, because model units vary wildly - metres for one author,
    // centimetres for the next. A fixed width blended the whole body to purple
    // on a model 1.8 units tall.
    const blend = height * 0.015;

    meshes.forEach((mesh) => {
      const source = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
      const base = source as THREE.MeshStandardMaterial;

      const material = new THREE.MeshToonMaterial({
        color: suit ? new THREE.Color(suit.top) : (base?.color?.clone() ?? new THREE.Color("#e62429")),
        map: suit ? null : (base?.map ?? null),
        gradientMap: ramp,
      });

      /** Paint the suit by height instead of by texture.
       *
       *  A downloaded humanoid arrives in whatever colour its author chose,
       *  usually as one material over the whole body, so there is no "legs"
       *  submesh to recolour. Splitting in the shader on the bind-pose Y gives
       *  a two-tone suit on any model — and using the bind pose rather than the
       *  skinned position is what stops the colours sliding around the body as
       *  the character moves, exactly as a texture would not. */
      if (suit) {
        material.onBeforeCompile = (shader) => {
          shader.uniforms.uSplit = { value: split };
          shader.uniforms.uBlend = { value: blend };
          shader.uniforms.uTop = { value: new THREE.Color(suit.top) };
          shader.uniforms.uBottom = { value: new THREE.Color(suit.bottom) };
          shader.vertexShader = shader.vertexShader
            .replace("#include <common>", "#include <common>\nvarying float vBindY;")
            .replace("#include <begin_vertex>", "#include <begin_vertex>\nvBindY = position.y;");
          shader.fragmentShader = shader.fragmentShader
            .replace(
              "#include <common>",
              "#include <common>\nvarying float vBindY;\nuniform float uSplit;\nuniform float uBlend;\nuniform vec3 uTop;\nuniform vec3 uBottom;",
            )
            .replace(
              "vec4 diffuseColor = vec4( diffuse, opacity );",
              "vec3 suitColour = mix( uBottom, uTop, smoothstep( uSplit - uBlend, uSplit + uBlend, vBindY ) );\nvec4 diffuseColor = vec4( suitColour, opacity );",
            );
        };
      }

      mesh.material = material;
      mesh.castShadow = true;

      if (!outline) return;
      // Back faces displaced along their own normals, in view space.
      //
      // Uniformly scaling a clone is the trick everyone reaches for first and
      // it only works when the geometry is centred on its own origin. On a
      // model whose parts sit far from theirs it throws each piece outward
      // instead of thickening it, which is what smeared black slabs behind
      // this character's arms. Displacement has to be per-vertex.
      const shell = mesh.clone() as THREE.Mesh;
      shell.material = new THREE.ShaderMaterial({
        uniforms: { uThickness: { value: outlineWidth } },
        vertexShader: `
          uniform float uThickness;
          void main() {
            vec4 view = modelViewMatrix * vec4( position, 1.0 );
            vec3 n = normalize( normalMatrix * normal );
            // Scaled by depth so the line keeps an even weight as it moves.
            view.xyz += n * uThickness * -view.z;
            gl_Position = projectionMatrix * view;
          }`,
        fragmentShader: `
          void main() { gl_FragColor = vec4( 0.043, 0.043, 0.059, 1.0 ); }`,
        side: THREE.BackSide,
      });
      if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) {
        (shell as THREE.SkinnedMesh).bind(
          (mesh as THREE.SkinnedMesh).skeleton,
          (mesh as THREE.SkinnedMesh).bindMatrix,
        );
      }
      outlines.push(shell);
      mesh.add(shell);
    });

    return () => outlines.forEach((o) => o.removeFromParent());
  }, [model, ramp, outline, outlineWidth, suit, suitSplit, hideBelowVerts]);

  /** The bone the web leaves from, resolved by name off the imported skeleton.
   *  Anchoring the strand to a fixed offset works until the figure moves — the
   *  whole point of a rigged model is that the hand has a real position. */
  const hand = useMemo(() => {
    const key = handBone.replace(/[^a-z0-9]/gi, "").toLowerCase();
    let found: THREE.Object3D | null = null;
    model.traverse((child) => {
      if (found) return;
      if (child.name.replace(/[^a-z0-9]/gi, "").toLowerCase().startsWith(key)) found = child;
    });
    return found as THREE.Object3D | null;
  }, [model, handBone]);

  const { actions, names } = useAnimations(animations, group);

  useEffect(() => {
    if (!names.length) return;
    const pick =
      CLIP_PREFERENCE.map((re) => names.find((n) => re.test(n))).find(Boolean) ?? names[0];
    const action = actions[pick];
    action?.reset().fadeIn(0.4).play();
    return () => {
      action?.fadeOut(0.3);
    };
  }, [actions, names]);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();

    // A gentle sway on top of whatever the clip does. A looping idle that never
    // drifts reads as a video; the drift is what sells it as hanging.
    if (group.current) {
      group.current.rotation.z = Math.sin(t * 0.55) * 0.05;
      group.current.rotation.y = Math.sin(t * 0.37) * 0.18;
      group.current.position.y = Math.sin(t * 0.7) * 0.03;
    }

    // One shot per cycle: a beat of nothing, the strand paying out fast, a hold,
    // then it lets go.
    const phase = (t % shootEvery) / shootEvery;
    let extend = 0;
    if (phase > 0.62 && phase < 0.78) {
      extend = 1 - Math.pow(1 - (phase - 0.62) / 0.16, 3);
    } else if (phase >= 0.78 && phase < 0.9) {
      extend = 1 - (phase - 0.78) / 0.12;
    }

    if (strand.current && stage.current) {
      strand.current.visible = extend > 0.04;
      if (splat.current) splat.current.visible = extend > 0.85;
      if (strand.current.visible) {
        // Read the hand's actual position and bring it into the group's space,
        // so the strand starts at the hand however the figure is posed, scaled
        // or swaying.
        if (hand) {
          hand.getWorldPosition(scratch.from);
          stage.current.worldToLocal(scratch.from);
        } else {
          scratch.from.set(0, 0, 0);
        }

        scratch.dir
          .set(webTarget[0], webTarget[1], webTarget[2])
          .sub(scratch.from)
          .multiplyScalar(extend);

        const length = Math.max(scratch.dir.length(), 1e-4);
        strand.current.position.copy(scratch.from).addScaledVector(scratch.dir, 0.5);
        strand.current.scale.set(1, length, 1);
        // A cylinder is built along Y, so align that axis with the throw.
        strand.current.quaternion.setFromUnitVectors(UP, scratch.dir.normalize());
        if (splat.current && splat.current.visible) {
          splat.current.position
            .copy(scratch.from)
            .addScaledVector(scratch.dir, length);
        }
      }
    }

    // Sound on the snap, once per cycle.
    if (phase > 0.63 && phase < 0.69) {
      if (!fired.current) {
        fired.current = true;
        thwip(0.85);
      }
    } else if (phase > 0.8 || phase < 0.6) {
      fired.current = false;
    }
  });

  return (
    // Pose and sway are separate groups on purpose: the frame loop writes
    // rotation every tick, so a resting attitude set on the same object would
    // be overwritten sixty times a second.
    // Three nested frames, each doing one job: `stage` is unrotated and owns
    // the web, `pose` turns the body, `group` carries the sway. Collapsing any
    // two of them turns the throw with the figure.
    <group ref={stage} scale={scale * targetHeight} dispose={null}>
      <group rotation={pose}>
        <group ref={group}>
          <Resize height precise>
            <Center precise>
              <primitive object={model} />
            </Center>
          </Resize>
        </group>
      </group>

      <mesh ref={strand} visible={false}>
        <cylinderGeometry args={[0.006, 0.013, 1, 6, 1]} />
        <meshBasicMaterial color={INK} />
      </mesh>
      {/* Where it lands. A strand that simply stops reads as unfinished. */}
      <mesh ref={splat} visible={false}>
        <sphereGeometry args={[0.05, 10, 8]} />
        <meshBasicMaterial color={INK} />
      </mesh>
    </group>
  );
}
