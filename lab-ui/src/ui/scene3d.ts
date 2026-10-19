/**
 * Scène three.js de la Vue 3D : le robot décrit en URDF, dessiné par la carte graphique de
 * l'étudiant (rien n'est calculé dans le conteneur). Chargée à la première ouverture de la vue.
 * ROS a l'axe z vers le haut : le robot est placé dans un groupe tourné pour three.js (y en haut).
 */
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import URDFLoader, { type URDFJoint, type URDFRobot } from "urdf-loader";
import type { Transform } from "../ros/robot";

export interface LoadedRobot {
  name: string;
  rootLink: string;
  links: string[];
  joints: URDFJoint[];
  /** Maillages (mesh) non affichés : seules les formes simples de l'URDF sont dessinées. */
  missingMeshes: number;
}

export class Scene3D {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene = new THREE.Scene();
  private readonly camera = new THREE.PerspectiveCamera(50, 1, 0.01, 200);
  private readonly controls: OrbitControls;
  /** Repère « fixe » de ROS (z en haut), tourné pour three.js. */
  private readonly world = new THREE.Group();
  /** Pose de la racine du robot dans le repère fixe (reçue par /tf, sinon l'origine). */
  private readonly base = new THREE.Group();
  private robot: URDFRobot | null = null;
  private frames: THREE.AxesHelper[] = [];
  private framesVisible = true;
  private frame: number | null = null;

  constructor(private readonly canvas: HTMLCanvasElement) {
    // lève une erreur si WebGL est indisponible : le panneau l'affiche
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.scene.background = new THREE.Color(0x101114);
    this.world.rotation.x = -Math.PI / 2;
    this.world.add(this.base, new THREE.AxesHelper(0.3));
    // sol : cases de 10 cm sur 4 m, et de 1 m jusqu'à 20 m
    const fine = new THREE.GridHelper(4, 40, 0x3a3b42, 0x1f2026);
    const large = new THREE.GridHelper(20, 20, 0x3a3b42, 0x3a3b42);
    this.scene.add(fine, large, this.world, new THREE.HemisphereLight(0xffffff, 0x2a2b31, 1.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.8);
    sun.position.set(3, 5, 4);
    this.scene.add(sun);
    this.camera.position.set(1.2, 0.9, 1.2);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.addEventListener("change", () => this.render());
    new ResizeObserver(() => this.resize()).observe(canvas);
  }

  /** Remplace le robot affiché ; renvoie ce qui a été chargé. */
  setRobot(urdf: string): LoadedRobot {
    let missingMeshes = 0;
    const loader = new URDFLoader();
    loader.parseCollision = false;
    loader.loadMeshCb = (_url, _manager, _material, done) => {
      missingMeshes += 1;
      done(new THREE.Object3D());
    };
    const robot = loader.parse(urdf);
    if (this.robot) this.base.remove(this.robot);
    this.robot = robot;
    this.base.add(robot);
    this.frames = Object.values(robot.links).map((link) => {
      const axes = new THREE.AxesHelper(0.08);
      axes.visible = this.framesVisible;
      link.add(axes);
      return axes;
    });
    this.fit();
    return {
      name: robot.robotName || "robot",
      rootLink: robot.urdfName,
      links: Object.keys(robot.links),
      joints: Object.values(robot.joints),
      missingMeshes,
    };
  }

  setJoints(values: Map<string, number>): void {
    if (!this.robot) return;
    let changed = false;
    for (const [name, value] of values) {
      if (name in this.robot.joints) changed = this.robot.setJointValue(name, value) || changed;
    }
    if (changed) this.render();
  }

  /** Pose de la racine du robot dans le repère fixe (null : à l'origine). */
  setRootPose(t: Transform | null): void {
    if (t) {
      this.base.position.set(t.translation.x, t.translation.y, t.translation.z);
      this.base.quaternion.set(t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w);
    } else {
      this.base.position.set(0, 0, 0);
      this.base.quaternion.identity();
    }
    this.render();
  }

  showFrames(on: boolean): void {
    this.framesVisible = on;
    for (const axes of this.frames) axes.visible = on;
    this.render();
  }

  /** Cadre la caméra sur le robot. */
  fit(): void {
    const box = new THREE.Box3().setFromObject(this.robot ?? this.world);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const size = Math.max(box.getSize(new THREE.Vector3()).length(), 0.2);
    const direction = new THREE.Vector3(1, 0.75, 1).normalize();
    this.camera.position.copy(center).addScaledVector(direction, size * 1.4);
    this.camera.near = size / 100;
    this.camera.far = size * 100 + 50;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.update();
    this.render();
  }

  resize(): void {
    const width = this.canvas.clientWidth;
    const height = this.canvas.clientHeight;
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.render();
  }

  /** Dessine à la prochaine image (une seule fois, même après plusieurs changements). */
  render(): void {
    this.frame ??= requestAnimationFrame(() => {
      this.frame = null;
      this.renderer.render(this.scene, this.camera);
    });
  }

  dispose(): void {
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.controls.dispose();
    this.renderer.dispose();
  }
}
