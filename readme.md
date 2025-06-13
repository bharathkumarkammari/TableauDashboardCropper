# Tableau Dashboard Cropper 🧩

A web-based application that allows users to export Tableau dashboards, crop chart sections interactively, and generate a Word report combining the cropped visuals and metadata.

---

## 🌐 Live Demo
🔗 [https://tableaudashboardcropper.onrender.com/login](https://tableaudashboardcropper.onrender.com/login)

---

## ✨ Key Features

- 🔐 Login with Tableau Online credentials (username/password)
- 📁 Select Project → Workbook → Dashboard using Tableau REST API
- 🖼️ Export dashboard to PDF → Convert to PNG → Crop interactively
- ✅ Cropped images previewed in real-time with confirmation
- 📝 Metadata shown next to cropped image (project, workbook, dashboard, timestamp)
- 📄 Generate Word report with all selected dashboards on one page (50% image left, 50% text right)
- 🧠 Prompt user for output filename before generating report
- 📦 Saves files to `output/` and shows download link

---

## 🖼️ Output Formats

- ✅ **PDF (.PDF)**
- ✅ **Word (.docx)** report with:
  - Export summary (timestamp + total dashboards)
  - Each cropped image aligned left
  - Corresponding metadata (Project, Workbook, Dashboard, Exported Time) aligned right
  - If two dashboards: both appear on the same page

---

## 🛠 Tech Stack

| Layer     | Technology              |
|-----------|--------------------------|
| Frontend  | HTML, CSS, JavaScript, Bootstrap |
| Backend   | Python, Flask           |
| Libraries | python-docx, Pillow, pdf2image, requests |
| Deploy    | [Render.com](https://render.com) (Free Tier) |

---

## 📁 Project Structure

```
📁 TableauDashboardCropper/
├── templates/              # HTML templates (index.html, login.html)
├── static/                 # CSS, JS, assets
├── output/                 # Final reports
├── uploads/                # Incoming/cropped PNGs
├── attached_assets/        # Static screenshots/docs
├── main.py                 # Entry point (Flask)
├── app.py                  # App controller logic
├── tableau_api.py          # Handles Tableau REST API auth + data
├── image_processor.py      # PNG cropping + formatting
├── requirements.txt
├── render.yaml
└── README.md
```

---

## 🚀 Deployment Instructions

## 🚀 How to Deploy (Render)

1. Push your app code to a public GitHub repo
2. Go to [Render](https://render.com), click **New Web Service**
3. Choose your repo, and enter the desired service name
4. Add a `render.yaml` file or use:
    ```
    buildCommand: ""
    startCommand: gunicorn main:app
    ```
5. App will be live at `https://<your-app>.onrender.com`

---

## 🧪 Local Setup (Optional)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up `poppler` (for PDF to image conversion)
3. Run locally:
   ```bash
   flask run
   ```
---

## 🧪 Sample Screenshots

| Cropper Interface | Combined Report |
|-------------------|-----------------|
| ![Crop](attached_assets/ui.png) | ![Report](attached_assets/report.png) |

---

## 🧑‍💻 Author

Built with ❤️ by [Bharath Kumar Kammari](https://bharathkumarkammari.com)

📧 Reach out for collaborations, improvements, or deployments!

