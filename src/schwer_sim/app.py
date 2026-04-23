from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog

from .sim import SchwerSimulation
from .persistence import ScenarioStore


class SchwerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Schwer Class Freighter Systems Simulator")
        self.geometry("1400x900")
        self.sim = SchwerSimulation(seed=42)
        self.speed = 1
        self.running = False

        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        controls = ttk.Frame(self)
        controls.pack(fill=tk.X)
        ttk.Button(controls, text="Step", command=lambda: self._step(1)).pack(side=tk.LEFT)
        ttk.Button(controls, text="Pause", command=lambda: self._set_running(False)).pack(side=tk.LEFT)
        ttk.Button(controls, text="1x", command=lambda: self._set_speed(1)).pack(side=tk.LEFT)
        ttk.Button(controls, text="10x", command=lambda: self._set_speed(10)).pack(side=tk.LEFT)
        ttk.Button(controls, text="100x", command=lambda: self._set_speed(100)).pack(side=tk.LEFT)
        ttk.Button(controls, text="Run", command=lambda: self._set_running(True)).pack(side=tk.LEFT)
        ttk.Button(controls, text="Save", command=self._save).pack(side=tk.LEFT)
        ttk.Button(controls, text="Load", command=self._load).pack(side=tk.LEFT)
        ttk.Button(controls, text="Inject Fault", command=self._inject_fault).pack(side=tk.LEFT)

        self.time_label = ttk.Label(controls, text="")
        self.time_label.pack(side=tk.RIGHT)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill=tk.BOTH, expand=True)
        self.views: dict[str, tk.Text] = {}
        for name in [
            "Ship Overview",
            "Power/Thermal",
            "Atmosphere/ECCS",
            "Propulsion",
            "Warp Readiness",
            "Cargo/Ballast",
            "Lighting/Display",
            "Maintenance Bay",
            "Alarm Log",
        ]:
            frame = ttk.Frame(self.tabs)
            self.tabs.add(frame, text=name)
            text = tk.Text(frame, wrap=tk.WORD)
            text.pack(fill=tk.BOTH, expand=True)
            self.views[name] = text

    def _set_speed(self, speed: int) -> None:
        self.speed = speed

    def _set_running(self, running: bool) -> None:
        self.running = running
        if running:
            self.after(100, self._tick)

    def _tick(self) -> None:
        if not self.running:
            return
        self._step(self.speed)
        self.after(100, self._tick)

    def _step(self, steps: int) -> None:
        self.sim.step(steps)
        self._refresh()

    def _inject_fault(self) -> None:
        self.sim.engine.schedule(0, "inject_fault", {"key": "radiator_damage"})

    def _save(self) -> None:
        target = filedialog.asksaveasfilename(defaultextension=".json")
        if not target:
            return
        ScenarioStore.save(target, {"name": "manual-save", "seed": self.sim.engine.seed}, self.sim.state)

    def _load(self) -> None:
        src = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not src:
            return
        metadata, state = ScenarioStore.load(src)
        self.sim = SchwerSimulation(seed=metadata.get("seed", 1), state=state)
        self._refresh()

    def _refresh(self) -> None:
        s = self.sim.state
        self.time_label.configure(text=f"t={s.time_s:,.0f}s")
        overview = (
            f"Main Domain MW: {s.main_power.electrical_mw:.1f}\n"
            f"Propulsion Domain MW: {s.propulsion_power.electrical_mw:.1f}\n"
            f"Warp Storage GJ: {s.warp.bulk_storage_gj:.1f}\n"
            f"Thermal margins: "
            + ", ".join(f"{k}={v.margin:.1f}" for k, v in s.thermal_loops.items())
        )
        pwr = (
            f"Main Reactor derate: {s.main_reactor.derate:.2f}\n"
            f"Main Thermal Margin: {s.thermal_loops['main'].margin:.2f} MW\n"
            f"Prop Thermal Margin: {s.thermal_loops['propulsion'].margin:.2f} MW\n"
            f"Warp Thermal Margin: {s.thermal_loops['warp'].margin:.2f} MW"
        )
        eccs = (
            f"Hab O2: {s.eccs.habitat.o2_kpa:.2f} kPa\nHab CO2: {s.eccs.habitat.co2_kpa:.2f} kPa\n"
            f"Humidity: {s.eccs.habitat.humidity_pct:.1f}%\nContam: {s.eccs.habitat.contamination_ppm:.1f} ppm"
        )
        prop = f"Mode: {s.propulsion.mode}\nThrust: {s.propulsion.thrust_kn:.1f} kN\nHot-section: {s.propulsion.hot_section_temp_c:.1f} C"
        warp = f"Authorized: {self.sim.warp_authorized()}\nReason: {s.warp.auth_reason or 'clear'}\nStage: {s.warp.stage}"
        cargo = (
            f"Mass: {s.cargo.mass_tonnes:.1f} t\nCentroid: {s.cargo.centroid_m:.2f} m\n"
            f"Moments P/Y/R: {s.cargo.pitch_moment:.1f}/{s.cargo.yaw_moment:.1f}/{s.cargo.roll_moment:.1f}"
        )
        light = (
            f"Egress routes lit: {s.lighting.lit_egress_routes}/{s.lighting.egress_routes}\n"
            f"DSC online: {s.signaling.dsc_online}\nEmergency signaling: {s.signaling.emergency_signaling_visible}"
        )
        maint = "\n".join(f"{k}: due@{v:.0f}s" for k, v in s.maintenance.items()) or "No scheduled maintenance"
        alarms = "\n".join(s.alarms) or "No active alarms"

        mapping = {
            "Ship Overview": overview,
            "Power/Thermal": pwr,
            "Atmosphere/ECCS": eccs,
            "Propulsion": prop,
            "Warp Readiness": warp,
            "Cargo/Ballast": cargo,
            "Lighting/Display": light,
            "Maintenance Bay": maint,
            "Alarm Log": alarms,
        }
        for name, text in mapping.items():
            w = self.views[name]
            w.delete("1.0", tk.END)
            w.insert("1.0", text)


def main() -> None:
    app = SchwerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
