import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from PIL import Image, ImageTk
from pdf2image import convert_from_path
from PyPDF2 import PdfMerger
from datetime import datetime
import json, os, requests, subprocess, shutil

# Tableau credentials (set after login)
TABLEAU_SERVER = "https://us-east-1.online.tableau.com"
TABLEAU_SITE = "your-site-name"
USERNAME = ""
PASSWORD = ""

# ----------------------------------------------
# AUTH + API HELPERS
# ----------------------------------------------
def get_auth_token():
    url = f"{TABLEAU_SERVER}/api/3.20/auth/signin"
    payload = {
        "credentials": {
            "name": USERNAME,
            "password": PASSWORD,
            "site": {"contentUrl": TABLEAU_SITE}
        }
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    resp = response.json()
    token = resp['credentials']['token']
    site_id = resp['credentials']['site']['id']
    user_id = resp['credentials']['user']['id']
    return token, site_id, user_id

def get_projects(token, site_id):
    url = f"{TABLEAU_SERVER}/api/3.20/sites/{site_id}/projects"
    headers = {"X-Tableau-Auth": token, "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["projects"]["project"]

def list_workbooks_in_project(token, site_id, project_name):
    projects = get_projects(token, site_id)
    project_id = next((p['id'] for p in projects if p['name'].lower() == project_name.lower()), None)
    if not project_id:
        return []
    url = f"{TABLEAU_SERVER}/api/3.20/sites/{site_id}/workbooks"
    headers = {"X-Tableau-Auth": token, "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    all_workbooks = response.json().get("workbooks", {}).get("workbook", [])
    return [wb for wb in all_workbooks if wb.get('project', {}).get('id') == project_id]

def get_views_in_workbook(token, site_id, workbook_id):
    url = f"{TABLEAU_SERVER}/api/3.20/sites/{site_id}/workbooks/{workbook_id}/views"
    headers = {"X-Tableau-Auth": token, "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["views"]["view"]

# ----------------------------------------------
# LOGIN AUTH
# ----------------------------------------------
def get_auth_token():
    url = f"{TABLEAU_SERVER}/api/3.20/auth/signin"
    payload = {
        "credentials": {
            "name": USERNAME,
            "password": PASSWORD,
            "site": {"contentUrl": TABLEAU_SITE}
        }
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    resp = response.json()
    token = resp['credentials']['token']
    site_id = resp['credentials']['site']['id']
    user_id = resp['credentials']['user']['id']
    return token, site_id, user_id

# ----------------------------------------------
# MAIN APPLICATION
# ----------------------------------------------
def launch_main_app():
    coords_file = "coords.json"
    coords = {}
    if os.path.exists(coords_file):
        with open(coords_file, "r") as f:
            coords = json.load(f)

    app = tk.Tk()
    app.title("Multi-Workbook Crop & Combine")
    app.geometry("800x850")

    sections = []
    project_map = {}

    main_top = tk.Frame(app)
    main_top.pack(pady=10)

    tk.Label(main_top, text="Select How Many Workbooks?").pack(side="left")
    count_var = tk.IntVar(value=2)
    count_dd = ttk.Combobox(main_top, textvariable=count_var, values=[1, 2, 3], state="readonly")
    count_dd.pack(side="left", padx=5)
    tk.Button(main_top, text="Go", command=lambda: reset_all()).pack(side="left", padx=5)

    frame = tk.Frame(app)
    frame.pack(fill="both", expand=True)

    def reset_all():
        for widget in frame.winfo_children():
            widget.destroy()
        sections.clear()
        generate_sections(count_var.get())

    def create_crop_section(frame, index):
        proj_var = tk.StringVar(value="Select Project")
        wb_var = tk.StringVar(value="Select Workbook")
        view_var = tk.StringVar(value="Select Dashboard")
        cropped_var = tk.StringVar(value="Not Cropped ❌")
        timestamp_var = tk.StringVar(value="Last Pulled: Not yet")
        tk.Label(frame, textvariable=timestamp_var, fg="gray").pack()
        preview_img = tk.Label(frame)
        preview_img.pack()

        ttk.Label(frame, text="Select Project").pack()
        proj_dd = ttk.Combobox(frame, textvariable=proj_var, state="readonly")
        proj_dd.pack()

        ttk.Label(frame, text="Select Workbook").pack()
        wb_dd = ttk.Combobox(frame, textvariable=wb_var, state="readonly")
        wb_dd.pack()

        ttk.Label(frame, text="Select Dashboard").pack()
        view_dd = ttk.Combobox(frame, textvariable=view_var, state="readonly")
        view_dd.pack()

        def load_workbooks(*_):
            project_name = proj_var.get()
            if not project_name or project_name == "Select Project":
                return
            token, site_id, _ = get_auth_token()
            wbs = list_workbooks_in_project(token, site_id, project_name)
            wb_names = ["Select Workbook"] + [w['name'] for w in wbs]
            wb_dd['values'] = wb_names
            wb_dd.map = {w['name']: w['id'] for w in wbs}
            wb_var.set("Select Workbook")

        def load_views(*_):
            wb_name = wb_var.get()
            if not wb_name or wb_name == "Select Workbook":
                return
            token, site_id, _ = get_auth_token()
            wb_id = wb_dd.map.get(wb_name)
            views = get_views_in_workbook(token, site_id, wb_id)
            view_names = ["Select Dashboard"] + [v['name'] for v in views]
            view_dd['values'] = view_names
            view_dd.map = {v['name']: v['id'] for v in views}
            view_var.set("Select Dashboard")

        proj_dd.bind("<<ComboboxSelected>>", load_workbooks)
        wb_dd.bind("<<ComboboxSelected>>", load_views)

        def export_and_crop():
            try:
                token, site_id, _ = get_auth_token()
                view_id = view_dd.map[view_var.get()]
                pdf_path = f"view_{index+1}.pdf"
                png_path = f"view_{index+1}.png"
                url = f"{TABLEAU_SERVER}/api/3.20/sites/{site_id}/views/{view_id}/pdf"
                response = requests.get(url, headers={"X-Tableau-Auth": token})
                response.raise_for_status()
                with open(pdf_path, "wb") as f:
                    f.write(response.content)
                img = convert_from_path(pdf_path, dpi=200)[0]
                img.save(png_path, "PNG")
                show_crop_interface(png_path, f"crop_{index+1}.png", cropped_var, preview_img)
                timestamp_var.set(f"Last Pulled: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        tk.Button(frame, text="Crop", command=export_and_crop).pack(pady=5)
        tk.Label(frame, textvariable=cropped_var, foreground="green").pack()

        return {
            "project": proj_var,
            "project_dropdown": proj_dd,
            "workbook": wb_var,
            "view": view_var,
            "cropped": cropped_var,
            "png_output": f"crop_{index+1}.png",
            "preview": preview_img
        }

    def show_crop_interface(img_path, output_path, cropped_var, preview_label):
        win = tk.Toplevel(app)
        img = Image.open(img_path)
        tk_img = ImageTk.PhotoImage(img)
        canvas = tk.Canvas(win, width=tk_img.width(), height=tk_img.height(), scrollregion=(0, 0, tk_img.width(), tk_img.height()), cursor="cross")
        h_scroll = tk.Scrollbar(win, orient="horizontal", command=canvas.xview)
        v_scroll = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        win.grid_rowconfigure(0, weight=1)
        win.grid_columnconfigure(0, weight=1)
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        rect = [None]
        coords_local = {}
        def on_down(e):
            coords_local['x1'], coords_local['y1'] = canvas.canvasx(e.x), canvas.canvasy(e.y)
            if rect[0]:
                canvas.delete(rect[0])
            rect[0] = canvas.create_rectangle(coords_local['x1'], coords_local['y1'], coords_local['x1'], coords_local['y1'], outline="red")
        def on_drag(e):
            x, y = canvas.canvasx(e.x), canvas.canvasy(e.y)
            canvas.coords(rect[0], coords_local['x1'], coords_local['y1'], x, y)
        def on_up(e):
            x2, y2 = canvas.canvasx(e.x), canvas.canvasy(e.y)
            x1, y1 = coords_local['x1'], coords_local['y1']
            cropped = img.crop((min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)))
            cropped.save(output_path)
            cropped_var.set("Cropped Image ✅")
            thumb = cropped.resize((200, 120))
            thumb_img = ImageTk.PhotoImage(thumb)
            preview_label.configure(image=thumb_img)
            preview_label.image = thumb_img
            win.destroy()
        canvas.bind("<Button-1>", on_down)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_up)
        win.mainloop()

    def combine_images():
        all_ready = all(sec['cropped'].get().startswith("Cropped") for sec in sections)
        if not all_ready:
            messagebox.showwarning("Wait", "Please crop all images first")
            return
        folder_name = "_".join([s['workbook'].get().replace(" ", "") for s in sections])
        os.makedirs(folder_name, exist_ok=True)
        output_pdf = filedialog.asksaveasfilename(initialdir=folder_name, defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], title="Save Combined PDF As")
        if not output_pdf:
            return
        summary_path = os.path.join(folder_name, "summary.txt")
        with open(summary_path, "w") as txt:
            for idx, s in enumerate(sections, 1):
                txt.write(f"[Section {idx}]\n")
                txt.write(f"Project: {s['project'].get()}\n")
                txt.write(f"Workbook: {s['workbook'].get()}\n")
                txt.write(f"Dashboard: {s['view'].get()}\n\n")
        merger = PdfMerger()
        temp_files = []
        for s in sections:
            img = Image.open(s['png_output']).convert("RGB")
            temp_pdf = s['png_output'].replace(".png", ".pdf")
            img.save(temp_pdf)
            merger.append(temp_pdf)
            temp_files.extend([s['png_output'], temp_pdf])
        merger.write(output_pdf)
        merger.close()
        for f in temp_files + [f"view_{i+1}.pdf" for i in range(len(sections))] + [f"view_{i+1}.png" for i in range(len(sections))]:
            if os.path.exists(f):
                os.remove(f)
        messagebox.showinfo("Done", f"PDF and summary saved in: {folder_name}")
        subprocess.run(["open" if os.name == "posix" else "start", output_pdf], shell=True)

    def generate_sections(count):
        for widget in frame.winfo_children():
            widget.destroy()
        sections.clear()
        token, site_id, _ = get_auth_token()
        projects = get_projects(token, site_id)
        nonlocal project_map
        project_map = {p['name']: p['id'] for p in projects}
        proj_names = ["Select Project"] + sorted(project_map.keys())
        for i in range(count):
            col_frame = tk.Frame(frame)
            col_frame.pack(side="left", expand=True, padx=20, pady=10)
            s = create_crop_section(col_frame, i)
            s['project_dropdown']['values'] = proj_names
            s['project_dropdown'].map = project_map
            sections.append(s)

    btn_frame = tk.Frame(app)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Combine", command=combine_images, bg="lightgreen").pack(side="left", padx=10)
    tk.Button(btn_frame, text="Reset", command=reset_all, bg="lightcoral").pack(side="right", padx=10)

    generate_sections(2)
    app.mainloop()

# ----------------------------------------------
# LOGIN WINDOW
# ----------------------------------------------
login_window = tk.Tk()
login_window.title("Tableau Login")
login_window.geometry("350x250")

site_var = tk.StringVar(value="your-site-name")
user_var = tk.StringVar()
pass_var = tk.StringVar()

def on_login():
    global USERNAME, PASSWORD, TABLEAU_SITE
    USERNAME = user_var.get()
    PASSWORD = pass_var.get()
    TABLEAU_SITE = site_var.get()
    try:
        get_auth_token()
        login_window.destroy()
        launch_main_app()
    except Exception as e:
        messagebox.showerror("Login Failed", str(e))

# LOGIN FORM UI
tk.Label(login_window, text="Tableau Username:").pack(pady=5)
tk.Entry(login_window, textvariable=user_var).pack()
tk.Label(login_window, text="Password:").pack(pady=5)
tk.Entry(login_window, textvariable=pass_var, show="*").pack()
tk.Label(login_window, text="Site URL Code (e.g., 'mysite'):").pack(pady=5)
tk.Entry(login_window, textvariable=site_var).pack()
tk.Button(login_window, text="Login", command=on_login).pack(pady=15)

login_window.mainloop()