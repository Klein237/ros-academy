/**
 * Vue 3D du lab : le robot décrit en URDF, dessiné dans le navigateur à partir de
 * /robot_description, /joint_states et /tf (par rosbridge). Elle remplace RViz pour voir un
 * modèle et ses articulations, sans bureau graphique ni calcul dans le conteneur.
 */
import {
  descriptionFromMessage,
  descriptionFromParameters,
  formatJoint,
  isMovable,
  jointPositions,
  jointStateMessage,
  sliderRange,
  transformTo,
} from "../ros/robot";
import type { RosbridgeClient, RosStatus } from "../ros/rosbridge";
import { button, h } from "./dom";
import type { LoadedRobot, Scene3D } from "./scene3d";

const STRING_TYPE = "std_msgs/msg/String";
const JOINT_STATE_TYPE = "sensor_msgs/msg/JointState";
const TF_TYPE = "tf2_msgs/msg/TFMessage";
const PARAMS_SERVICE = "/robot_state_publisher/get_parameters";
const POLL_MS = 3000;
const PUBLISH_MS = 200;

interface Slider {
  input: HTMLInputElement;
  value: HTMLElement;
  joint: LoadedRobot["joints"][number];
}

export class View3DPanel {
  readonly el = h("section", { class: "panel view3d", attrs: { "aria-label": "Vue 3D", hidden: "" } });
  private readonly canvas = h("canvas", { class: "view3d-canvas", attrs: { "aria-label": "Robot en 3D" } });
  private readonly status = h("span", { class: "pill", text: "en attente du modèle" });
  private readonly hint = h("p", { class: "view3d-hint muted small" });
  private readonly readout = h("p", { class: "view3d-readout muted small" });
  private readonly jointsList = h("div", { class: "view3d-joints" });
  private readonly publishBox = h("input", { type: "checkbox", attrs: { "aria-label": "Publier sur /joint_states" } });
  private readonly descriptionInput = h("input", {
    attrs: { value: "/robot_description", "aria-label": "Topic de la description", spellcheck: "false" },
  });
  private readonly jointsInput = h("input", {
    attrs: { value: "/joint_states", "aria-label": "Topic de l'état des joints", spellcheck: "false" },
  });
  private readonly framesButton: HTMLButtonElement;
  /** Curseurs déplacés à la main : la vue cesse de suivre /joint_states jusqu'au clic sur ce bouton. */
  private readonly followButton: HTMLButtonElement;
  private manual = false;
  private scene: Scene3D | null = null;
  private loading: Promise<Scene3D | null> | null = null;
  private robot: LoadedRobot | null = null;
  private description = "";
  private sliders = new Map<string, Slider>();
  private values = new Map<string, number>();
  private jointMessages = 0;
  private unsubscribers: (() => void)[] = [];
  private pollTimer: number | null = null;
  private publishTimer: number | null = null;
  private dragging: string | null = null;

  constructor(private readonly ros: RosbridgeClient) {
    this.framesButton = button("Repères", () => this.toggleFrames(), { class: "small", attrs: { "aria-pressed": "true" } });
    this.followButton = button("Suivre /joint_states", () => this.setManual(false), { class: "small", attrs: { hidden: "" } });
    this.publishBox.addEventListener("change", () => this.setPublishing(this.publishBox.checked));
    this.descriptionInput.addEventListener("change", () => this.reload());
    this.jointsInput.addEventListener("change", () => this.subscribe());
    this.el.append(
      h(
        "div",
        { class: "panel-header" },
        h("h2", { text: "Vue 3D" }),
        this.status,
        h("span", { class: "spacer" }),
        this.framesButton,
        button("Recadrer", () => this.scene?.fit(), { class: "small" }),
        button("Recharger le modèle", () => this.reload(), { class: "small" }),
      ),
      h(
        "div",
        { class: "view3d-body" },
        h("div", { class: "view3d-stage" }, this.canvas, this.hint),
        h(
          "aside",
          { class: "view3d-side" },
          this.readout,
          h("h3", { text: "Articulations" }),
          this.jointsList,
          this.followButton,
          h(
            "label",
            { class: "view3d-publish small", title: "Comme joint_state_publisher_gui : à utiliser sans joint_state_publisher, sinon les deux se contredisent" },
            this.publishBox,
            " Publier sur /joint_states",
          ),
          h(
            "div",
            { class: "view-settings" },
            h("label", {}, "Description ", this.descriptionInput),
            h("label", {}, "Joints ", this.jointsInput),
          ),
        ),
      ),
    );
    this.setHint();
  }

  get visible(): boolean {
    return !this.el.hidden;
  }

  /** Affiche la vue : charge three.js la première fois, puis s'abonne aux topics du robot. */
  show(): void {
    this.el.hidden = false;
    void this.ensureScene().then((scene) => {
      if (!scene || !this.visible) return;
      scene.resize();
      this.subscribe();
      this.startPolling();
    });
  }

  /** Masque la vue : plus d'abonnement tant qu'elle est cachée. */
  hide(): void {
    this.el.hidden = true;
    this.unsubscribe();
    this.stopPolling();
    this.setPublishing(false);
  }

  setStatus(status: RosStatus): void {
    if (status === "open" && this.visible && !this.robot) void this.pollDescription();
  }

  dispose(): void {
    this.hide();
    this.scene?.dispose();
    this.scene = null;
  }

  private ensureScene(): Promise<Scene3D | null> {
    this.loading ??= import("./scene3d")
      .then(({ Scene3D }) => (this.scene = new Scene3D(this.canvas)))
      .catch((e) => {
        console.warn("Vue 3D indisponible", e);
        this.setState("indisponible", "Ce navigateur n'affiche pas la 3D (WebGL désactivé ?). RViz reste disponible sur le Bureau.");
        return null;
      });
    return this.loading;
  }

  private subscribe(): void {
    this.unsubscribe();
    const descriptionTopic = this.descriptionInput.value.trim() || "/robot_description";
    const jointsTopic = this.jointsInput.value.trim() || "/joint_states";
    this.unsubscribers = [
      this.ros.subscribe(descriptionTopic, STRING_TYPE, (msg) => this.onDescription(descriptionFromMessage(msg))),
      this.ros.subscribe(jointsTopic, JOINT_STATE_TYPE, (msg) => this.onJointState(msg), 30),
      this.ros.subscribe("/tf", TF_TYPE, (msg) => this.onTf(msg), 50),
    ];
  }

  private unsubscribe(): void {
    for (const off of this.unsubscribers.splice(0)) off();
  }

  /**
   * /robot_description est publié une seule fois, au démarrage de robot_state_publisher : un
   * abonnement arrivé trop tôt ou trop tard peut le manquer. Tant que le modèle manque, on le
   * demande aussi au nœud (paramètre robot_description).
   */
  private startPolling(): void {
    this.stopPolling();
    void this.pollDescription();
    this.pollTimer = window.setInterval(() => {
      if (!this.robot) void this.pollDescription();
    }, POLL_MS);
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) clearInterval(this.pollTimer);
    this.pollTimer = null;
  }

  private async pollDescription(): Promise<void> {
    if (this.ros.status !== "open") return;
    try {
      const values = await this.ros.callService(PARAMS_SERVICE, { names: ["robot_description"] }, 2500);
      this.onDescription(descriptionFromParameters(values));
    } catch {
      // robot_state_publisher pas encore lancé : on réessaie
    }
  }

  private reload(): void {
    this.description = "";
    this.robot = null;
    this.setHint();
    if (this.visible && this.scene) {
      this.subscribe();
      this.startPolling();
    }
  }

  private onDescription(urdf: string | null): void {
    if (!urdf || urdf === this.description || !this.scene) return;
    let robot: LoadedRobot;
    try {
      robot = this.scene.setRobot(urdf);
    } catch (e) {
      console.warn("Vue 3D : description illisible", e);
      this.setState("erreur", "La description reçue n'est pas un URDF lisible. Vérifiez-la avec check_urdf.");
      return;
    }
    this.description = urdf;
    this.robot = robot;
    this.el.dataset.model = robot.name;
    this.el.dataset.links = String(robot.links.length);
    this.buildSliders(robot);
    this.scene.setJoints(this.values);
    const movable = robot.joints.filter(isMovable).length;
    this.setState(
      "pret",
      robot.missingMeshes
        ? `${robot.missingMeshes} maillage(s) non affiché(s) : la Vue 3D dessine les formes simples (box, cylinder, sphere).`
        : "",
    );
    this.status.textContent = `${robot.name} · ${robot.links.length} links · ${movable} joint${movable > 1 ? "s" : ""} mobile${movable > 1 ? "s" : ""}`;
  }

  private onJointState(msg: unknown): void {
    if (this.manual || this.publishTimer !== null) return; // les curseurs décident
    const positions = jointPositions(msg);
    if (!positions.size) return;
    this.jointMessages += 1;
    this.el.dataset.jointStates = String(this.jointMessages);
    for (const [name, value] of positions) {
      this.values.set(name, value);
      const slider = this.sliders.get(name);
      if (slider && this.dragging !== name) this.showValue(slider, value);
    }
    this.scene?.setJoints(positions);
  }

  private onTf(msg: unknown): void {
    if (!this.robot) return;
    const found = transformTo(msg, this.robot.rootLink);
    if (!found || this.robot.links.includes(found.parent)) return;
    this.scene?.setRootPose(found.transform);
    this.readout.textContent = `Repère fixe : ${found.parent} → ${this.robot.rootLink}`;
  }

  private buildSliders(robot: LoadedRobot): void {
    this.sliders.clear();
    const movable = robot.joints.filter(isMovable);
    const rows = movable.map((joint) => {
      const [min, max] = sliderRange(joint);
      const input = h("input", {
        type: "range",
        attrs: { min: String(min), max: String(max), step: String((max - min) / 400), "aria-label": `Joint ${joint.urdfName}` },
      });
      const value = h("span", { class: "view3d-value" });
      const slider = { input, value, joint };
      this.sliders.set(joint.urdfName, slider);
      this.showValue(slider, this.values.get(joint.urdfName) ?? 0);
      input.addEventListener("pointerdown", () => (this.dragging = joint.urdfName));
      input.addEventListener("change", () => (this.dragging = null));
      input.addEventListener("input", () => {
        const v = Number(input.value);
        this.values.set(joint.urdfName, v);
        this.setManual(true);
        value.textContent = formatJoint(joint, v);
        this.scene?.setJoints(new Map([[joint.urdfName, v]]));
        if (this.publishTimer !== null) this.publishJoints();
      });
      return h("label", { class: "view3d-joint" }, h("code", { text: joint.urdfName }), value, input);
    });
    this.jointsList.replaceChildren(
      ...(rows.length ? rows : [h("p", { class: "muted small", text: "Aucun joint mobile : tous les joints sont fixes." })]),
    );
    this.readout.textContent = `Racine : ${robot.rootLink}`;
  }

  private showValue(slider: Slider, v: number): void {
    slider.input.value = String(v);
    slider.value.textContent = formatJoint(slider.joint, v);
  }

  /** Publie la position des curseurs, comme joint_state_publisher_gui (5 fois par seconde). */
  private setPublishing(on: boolean): void {
    this.publishBox.checked = on;
    if (this.publishTimer !== null) clearInterval(this.publishTimer);
    this.publishTimer = null;
    if (on) {
      this.publishJoints();
      this.publishTimer = window.setInterval(() => this.publishJoints(), PUBLISH_MS);
    }
    this.setManual(this.manual);
  }

  private publishJoints(): void {
    const values = new Map<string, number>();
    for (const [name, slider] of this.sliders) values.set(name, this.values.get(name) ?? Number(slider.input.value));
    if (!values.size) return;
    this.ros.publish(this.jointsInput.value.trim() || "/joint_states", JOINT_STATE_TYPE, jointStateMessage(values));
  }

  private setManual(on: boolean): void {
    this.manual = on;
    this.followButton.hidden = !on || this.publishTimer !== null;
  }

  private toggleFrames(): void {
    const on = this.framesButton.getAttribute("aria-pressed") !== "true";
    this.framesButton.setAttribute("aria-pressed", String(on));
    this.scene?.showFrames(on);
  }

  private setState(state: string, hint: string): void {
    this.el.dataset.state = state;
    this.hint.textContent = hint;
    this.hint.hidden = !hint;
  }

  private setHint(): void {
    delete this.el.dataset.model;
    this.status.textContent = "en attente du modèle";
    this.setState(
      "attente",
      "En attente de /robot_description… Lancez par exemple « ros2 launch my_robot_description display.launch.py » dans un terminal.",
    );
  }
}
