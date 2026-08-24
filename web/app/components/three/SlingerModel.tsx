"use client";

import { useEffect, useMemo, useRef } from "react";
import { Center, Resize, useAnimations, useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { SkeletonUtils } from "three-stdlib";

/** Renders a rigged humanoid from a glTF file, shaded to match the page. */

const INK = "#0b0b0f";

/** Clip names vary by author. */
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
  suit = null,
  suitSplit = 0.52,
  targetHeight = 3,
  outlineWidth = 0.004,
  pose = [0, 0, 0],
  hideBelowVerts = 0,
}: {
  url: string;
  scale?: number;
  outline?: boolean;
  /** Two-tone suit. */
  suit?: { top: string; bottom: string } | null;
  /** Height of the colour break, 0 at the feet and 1 at the crown. */
  suitSplit?: number;
  /** World height the model is normalised to, whatever it was exported at. */
  targetHeight?: number;
  /** Ink line weight, as a fraction of view depth. */
  outlineWidth?: number;
  /** Resting rotation. */
  pose?: [number, number, number];
  /** Drop meshes below this vertex count. */
  hideBelowVerts?: number;
}) {
  const stage = useRef<THREE.Group>(null);
  const group = useRef<THREE.Group>(null);
  // Draco-compressed geometry, with the decoder served from this origin.
  const { scene, animations } = useGLTF(url, "/draco/");

  // Skinned meshes cannot be shared between renderers by reference — cloning the scene
  // graph normally leaves both copies driven by one skeleton.
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

    // Collect first.
    const meshes: THREE.Mesh[] = [];
    model.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) meshes.push(child as THREE.Mesh);
    });

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
    // centimetres for the next.
    const blend = height * 0.015;

    meshes.forEach((mesh) => {
      const source = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
      const base = source as THREE.MeshStandardMaterial;

      const material = new THREE.MeshToonMaterial({
        color: suit ? new THREE.Color(suit.top) : (base?.color?.clone() ?? new THREE.Color("#e62429")),
        map: suit ? null : (base?.map ?? null),
        gradientMap: ramp,
      });

      /** Paint the suit by height instead of by texture. */
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
      const shell = mesh.clone() as THREE.Mesh;
      // clone() copies the transform, and the shell is then parented *to* the mesh — so
      // the mesh's own transform lands on it twice.
      shell.position.set(0, 0, 0);
      shell.rotation.set(0, 0, 0);
      shell.scale.set(1, 1, 1);
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

    // Sway and drift only.
    if (group.current) {
      group.current.rotation.z = Math.sin(t * 0.55) * 0.05;
      group.current.rotation.y = Math.sin(t * 0.37) * 0.18;
      group.current.position.y = Math.sin(t * 0.7) * 0.03;
    }
  });

  return (
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
    </group>
  );
}
