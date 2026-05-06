"""
GPS Spoof module GUI — self-contained config dialog with interactive map.

Called by the INDRA GUI when the gps_spoof module is selected.
The main entry point is ``prompt_config(parent)``, which opens a modal
dialog and returns a dict of parameters (or None if cancelled).
"""

import tkinter as tk
from tkinter import filedialog
import ttkbootstrap as tb
import tkintermapview
import geocoder


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_real_location():
    """
    Attempts to determine the device's real location via IP geolocation.
    Returns (lat, lon) or (None, None) on failure.
    """
    try:
        g = geocoder.ip('me')
        if g.ok and g.latlng:
            return g.latlng[0], g.latlng[1]
    except Exception:
        pass
    return None, None


# ── Public API ─────────────────────────────────────────────────────────────────

def prompt_config(parent):
    """
    Opens a modal dialog on *parent* with GPS spoofing parameters on the
    left and an interactive map on the right showing real (green) vs
    spoofed (red) coordinates.

    Returns:
        dict  with keys latitude, longitude, altitude, tx_power
        None  if the user cancels
    """

    result = {}

    # Borrow font objects from the parent IndraGUI
    label_font = getattr(parent, "label_font", ("Consolas", 10))
    exploit_font = getattr(parent, "exploit_font", ("Consolas", 24, "bold"))
    selected_module = None
    try:
        selected_module = parent.selected_module.get()
    except Exception:
        selected_module = None
    is_dynamic_mode = selected_module == "gps_spoof_dynamic"

    # --- Detect real location ---
    real_lat, real_lon = _get_real_location()
    has_real = real_lat is not None and real_lon is not None

    # Default spoofed coords
    default_spoof_lat = "40.7128"
    default_spoof_lon = "-74.0060"

    # --- Dialog window ---
    dialog = tb.Toplevel(parent)
    dialog.title("GPS Spoof \u2014 Map View")
    dialog.geometry("960x580")
    dialog.resizable(False, False)
    dialog.grab_set()

    # Two-column layout: left = form, right = map
    dialog.grid_columnconfigure(0, weight=0, minsize=320)
    dialog.grid_columnconfigure(1, weight=1)
    dialog.grid_rowconfigure(0, weight=1)

    # ── Left panel: form ──────────────────────────────────────────────────
    left = tb.Frame(dialog)
    left.grid(row=0, column=0, sticky="nsew", padx=(15, 5), pady=15)

    tb.Label(left, text="GPS Spoofing", font=exploit_font,
             bootstyle="danger").pack(pady=(0, 12))

    form = tb.Frame(left)
    form.pack(fill=tk.X)
    form.grid_columnconfigure(1, weight=1)

    tb.Label(form, text="Latitude:", font=label_font).grid(
        row=0, column=0, sticky="w", pady=4)
    lat_entry = tb.Entry(form, font=label_font, bootstyle="danger")
    lat_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
    lat_entry.insert(0, default_spoof_lat)

    tb.Label(form, text="Longitude:", font=label_font).grid(
        row=1, column=0, sticky="w", pady=4)
    lon_entry = tb.Entry(form, font=label_font, bootstyle="danger")
    lon_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=4)
    lon_entry.insert(0, default_spoof_lon)

    tb.Label(form, text="Altitude (m):", font=label_font).grid(
        row=2, column=0, sticky="w", pady=4)
    alt_entry = tb.Entry(form, font=label_font, bootstyle="danger")
    alt_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=4)
    alt_entry.insert(0, "100")

    tb.Label(form, text="TX Power (0-47):", font=label_font).grid(
        row=3, column=0, sticky="w", pady=4)
    power_entry = tb.Entry(form, font=label_font, bootstyle="danger")
    power_entry.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=4)
    power_entry.insert(0, "0")

    csv_entry = None
    if is_dynamic_mode:
        tb.Label(form, text="Trajectory CSV:", font=label_font).grid(
            row=4, column=0, sticky="w", pady=4)

        csv_container = tb.Frame(form)
        csv_container.grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=4)
        csv_container.grid_columnconfigure(0, weight=1)

        csv_entry = tb.Entry(csv_container, font=label_font, bootstyle="danger")
        csv_entry.grid(row=0, column=0, sticky="ew")

        def _browse_csv():
            selected_file = filedialog.askopenfilename(
                parent=dialog,
                title="Select trajectory CSV",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if selected_file:
                csv_entry.delete(0, tk.END)
                csv_entry.insert(0, selected_file)

        tb.Button(
            csv_container,
            text="Browse",
            bootstyle="secondary",
            command=_browse_csv,
            width=9,
        ).grid(row=0, column=1, padx=(8, 0))

        tb.Label(
            left,
              text="Optional CSV enables trajectory mode\n"
                  "(time,x,y,z) or (time,lat,lon,height).\n"
                  "Leave blank to auto-generate a straight path\n"
                  "from the start coordinates.",
            font=label_font,
            bootstyle="info",
            justify=tk.LEFT,
        ).pack(pady=(10, 0), anchor="w")

    # Real-location info label
    if has_real:
        real_text = f"Real location (IP):  {real_lat:.4f}, {real_lon:.4f}"
    else:
        real_text = "Real location: unavailable"
    tb.Label(left, text=real_text, font=label_font,
             bootstyle="success").pack(pady=(18, 2), anchor="w")

    # Legend
    legend = tb.Frame(left)
    legend.pack(anchor="w", pady=(4, 0))
    tb.Label(legend, text="\u25cf", foreground="#00c000",
             font=label_font).pack(side=tk.LEFT)
    tb.Label(legend, text=" Real   ", font=label_font).pack(side=tk.LEFT)
    tb.Label(legend, text="\u25cf", foreground="#c00000",
             font=label_font).pack(side=tk.LEFT)
    tb.Label(legend, text=" Spoofed", font=label_font).pack(side=tk.LEFT)

    # Buttons
    def on_confirm():
        if is_dynamic_mode:
            csv_path = csv_entry.get().strip() if csv_entry is not None else ""
            result["csv_file"] = csv_path

        result["latitude"] = lat_entry.get().strip()
        result["longitude"] = lon_entry.get().strip()
        result["altitude"] = alt_entry.get().strip()
        result["tx_power"] = power_entry.get().strip()
        dialog.destroy()

    def on_cancel():
        dialog.destroy()

    btn_frame = tb.Frame(left)
    btn_frame.pack(pady=20)
    tb.Button(btn_frame, text="Launch", bootstyle="danger",
              command=on_confirm).pack(side=tk.LEFT, padx=10)
    tb.Button(btn_frame, text="Cancel", bootstyle="secondary",
              command=on_cancel).pack(side=tk.LEFT, padx=10)

    # ── Right panel: map ──────────────────────────────────────────────────
    map_widget = tkintermapview.TkinterMapView(dialog, width=600, height=550)
    map_widget.grid(row=0, column=1, sticky="nsew", padx=(5, 15), pady=15)

    # Initial map position centred on spoofed location
    spoof_lat_init = float(default_spoof_lat)
    spoof_lon_init = float(default_spoof_lon)
    map_widget.set_position(spoof_lat_init, spoof_lon_init)
    map_widget.set_zoom(5)

    # Place markers
    if has_real:
        map_widget.set_marker(real_lat, real_lon,
                              text="Real Location",
                              marker_color_circle="green",
                              marker_color_outside="darkgreen")

    spoof_marker = map_widget.set_marker(spoof_lat_init, spoof_lon_init,
                                         text="Spoofed Location",
                                         marker_color_circle="red",
                                         marker_color_outside="darkred")

    # Draw a line between real and spoofed if both exist
    path_line = None
    if has_real:
        path_line = map_widget.set_path([
            (real_lat, real_lon),
            (spoof_lat_init, spoof_lon_init)
        ], color="red", width=2)

    # ── Update spoofed marker when entries change ──────────────────────
    def _update_spoof_marker(*_args):
        nonlocal spoof_marker, path_line
        try:
            new_lat = float(lat_entry.get().strip())
            new_lon = float(lon_entry.get().strip())
        except (ValueError, TypeError):
            return
        spoof_marker.set_position(new_lat, new_lon)
        if has_real and path_line is not None:
            path_line.set_position_list([
                (real_lat, real_lon),
                (new_lat, new_lon)
            ])

    lat_entry.bind("<KeyRelease>", _update_spoof_marker)
    lon_entry.bind("<KeyRelease>", _update_spoof_marker)

    # Allow clicking the map to set spoofed coordinates
    def _on_map_click(coords):
        lat_entry.delete(0, tk.END)
        lat_entry.insert(0, f"{coords[0]:.6f}")
        lon_entry.delete(0, tk.END)
        lon_entry.insert(0, f"{coords[1]:.6f}")
        _update_spoof_marker()

    map_widget.add_left_click_map_command(_on_map_click)

    # ── Block until dialog closes ─────────────────────────────────────────
    parent.wait_window(dialog)

    return result if result else None
