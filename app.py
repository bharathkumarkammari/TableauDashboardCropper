import os
import logging
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime
import json
import shutil

from tableau_api import TableauAPI
from image_processor import ImageProcessor

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "fallback-secret-key-for-dev")

# Configure upload and output folders
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if 'tableau_token' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        site_id = request.form['site_id']
        server_url = request.form.get('server_url', 'https://us-east-1.online.tableau.com')
        
        try:
            tableau = TableauAPI(server_url, site_id)
            token, site_id_response, user_id = tableau.authenticate(username, password)
            
            # Store authentication info in session
            session['tableau_token'] = token
            session['tableau_site_id'] = site_id_response
            session['tableau_user_id'] = user_id
            session['tableau_server'] = server_url
            session['tableau_site'] = site_id
            session['username'] = username
            
            flash('Successfully logged in to Tableau!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
            logging.error(f"Login error: {str(e)}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/set_workbook_count', methods=['POST'])
def set_workbook_count():
    count = int(request.form.get('count', 2))
    session['workbook_count'] = count
    session['workbooks'] = []
    session['cropped_images'] = {}
    
    # Initialize workbook data structure
    for i in range(count):
        session['workbooks'].append({
            'index': i,
            'project': '',
            'workbook': '',
            'dashboard': '',
            'cropped': False,
            'timestamp': None
        })
    
    return redirect(url_for('index'))

@app.route('/get_projects')
def get_projects():
    if 'tableau_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        tableau = TableauAPI(session['tableau_server'], session['tableau_site'])
        tableau.token = session['tableau_token']
        tableau.site_id_response = session['tableau_site_id']
        tableau.user_id = session['tableau_user_id']
        
        projects = tableau.get_projects()
        return jsonify({'projects': projects})
    except Exception as e:
        logging.error(f"Error getting projects: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_workbooks/<project_name>')
def get_workbooks(project_name):
    if 'tableau_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        tableau = TableauAPI(session['tableau_server'], session['tableau_site'])
        tableau.token = session['tableau_token']
        tableau.site_id_response = session['tableau_site_id']
        tableau.user_id = session['tableau_user_id']
        
        workbooks = tableau.list_workbooks_in_project(project_name)
        return jsonify({'workbooks': workbooks})
    except Exception as e:
        logging.error(f"Error getting workbooks: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_dashboards/<workbook_id>')
def get_dashboards(workbook_id):
    if 'tableau_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        tableau = TableauAPI(session['tableau_server'], session['tableau_site'])
        tableau.token = session['tableau_token']
        tableau.site_id_response = session['tableau_site_id']
        tableau.user_id = session['tableau_user_id']
        
        dashboards = tableau.get_views_in_workbook(workbook_id)
        return jsonify({'dashboards': dashboards})
    except Exception as e:
        logging.error(f"Error getting dashboards: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/export_dashboard', methods=['POST'])
def export_dashboard():
    if 'tableau_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        view_id = data['view_id']
        workbook_index = data['workbook_index']
        project_name = data.get('project_name', 'Unknown')
        workbook_name = data.get('workbook_name', 'Unknown')
        dashboard_name = data.get('dashboard_name', 'Unknown')
        
        tableau = TableauAPI(session['tableau_server'], session['tableau_site'])
        tableau.token = session['tableau_token']
        tableau.site_id_response = session['tableau_site_id']
        tableau.user_id = session['tableau_user_id']
        
        # Export as PDF
        pdf_content = tableau.export_view_as_pdf(view_id)
        pdf_filename = f"dashboard_{workbook_index}_{datetime.now().timestamp()}.pdf"
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
        
        with open(pdf_path, 'wb') as f:
            f.write(pdf_content)
        
        # Convert PDF to PNG
        processor = ImageProcessor()
        png_path = processor.pdf_to_png(pdf_path)
        
        # Update session data
        if 'workbooks' not in session:
            session['workbooks'] = []
        
        while len(session['workbooks']) <= workbook_index:
            session['workbooks'].append({})
        
        session['workbooks'][workbook_index]['pdf_path'] = pdf_path
        session['workbooks'][workbook_index]['png_path'] = png_path
        session['workbooks'][workbook_index]['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        session['workbooks'][workbook_index]['project'] = project_name
        session['workbooks'][workbook_index]['workbook'] = workbook_name
        session['workbooks'][workbook_index]['dashboard'] = dashboard_name
        session.modified = True
        
        return jsonify({
            'success': True,
            'png_filename': os.path.basename(png_path),
            'timestamp': session['workbooks'][workbook_index]['timestamp']
        })
        
    except Exception as e:
        logging.error(f"Error exporting dashboard: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/crop/<int:workbook_index>')
def crop_image(workbook_index):
    if 'tableau_token' not in session:
        return redirect(url_for('login'))
    
    if 'workbooks' not in session or workbook_index >= len(session['workbooks']):
        flash('Invalid workbook index', 'error')
        return redirect(url_for('index'))
    
    workbook = session['workbooks'][workbook_index]
    if 'png_path' not in workbook:
        flash('No image to crop for this workbook', 'error')
        return redirect(url_for('index'))
    
    png_filename = os.path.basename(workbook['png_path'])
    return render_template('crop.html', 
                         workbook_index=workbook_index, 
                         png_filename=png_filename,
                         workbook=workbook)

@app.route('/save_crop', methods=['POST'])
def save_crop():
    if 'tableau_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        workbook_index = data['workbook_index']
        crop_data = data['crop_data']
        
        workbook = session['workbooks'][workbook_index]
        original_path = workbook['png_path']
        
        # Process the cropped image
        processor = ImageProcessor()
        cropped_path = processor.crop_image(original_path, crop_data)
        
        # Create thumbnail for preview
        thumbnail_path = processor.create_thumbnail(cropped_path)
        
        # Update session
        session['workbooks'][workbook_index]['cropped_path'] = cropped_path
        session['workbooks'][workbook_index]['thumbnail_path'] = thumbnail_path
        session['workbooks'][workbook_index]['cropped'] = True
        session.modified = True
        
        return jsonify({
            'success': True, 
            'cropped_filename': os.path.basename(cropped_path),
            'thumbnail_filename': os.path.basename(thumbnail_path)
        })
        
    except Exception as e:
        logging.error(f"Error saving crop: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/combine', methods=['POST'])
def combine_images():
    if 'tableau_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'workbooks' not in session:
        return jsonify({'error': 'No workbooks selected'}), 400
    
    # Check if all images are cropped
    for workbook in session['workbooks']:
        if not workbook.get('cropped', False):
            return jsonify({'error': 'Please crop all images before combining'}), 400
    
    try:
        # Get data from JSON request
        data = request.get_json()
        output_format = data.get('format', 'pdf')
        custom_filename = data.get('filename', 'dashboard_report')
        
        # Remove extension from filename if provided
        base_filename = custom_filename
        if custom_filename.endswith('.pdf') or custom_filename.endswith('.docx'):
            base_filename = os.path.splitext(custom_filename)[0]
        
        # Use default filename if empty
        if not base_filename.strip():
            base_filename = 'tableau_report'
        
        processor = ImageProcessor()
        
        # Get cropped image paths
        cropped_paths = [wb['cropped_path'] for wb in session['workbooks'] if wb.get('cropped_path')]
        
        if not cropped_paths:
            return jsonify({'error': 'No cropped images found'}), 400
        
        # Create temporary output directory
        temp_dir = os.path.join(app.config['OUTPUT_FOLDER'], 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate summary data for Word document
        summary_data = []
        for i, wb in enumerate(session['workbooks']):
            summary_data.append({
                'section': i + 1,
                'project': wb.get('project', 'Unknown'),
                'workbook': wb.get('workbook', 'Unknown'), 
                'dashboard': wb.get('dashboard', 'Unknown'),
                'timestamp': wb.get('timestamp', 'Unknown'),
                'image_path': wb.get('cropped_path', '')
            })
        
        # Combine images
        if output_format == 'pdf':
            output_path = processor.combine_to_pdf(cropped_paths, temp_dir, base_filename)
        else:
            output_path = processor.combine_to_word_with_details(cropped_paths, temp_dir, base_filename, summary_data)
        
        # Return file for download
        def cleanup_after_download():
            # Clean up temporary files after a delay
            import threading
            import time
            def delayed_cleanup():
                time.sleep(30)  # Wait 30 seconds before cleanup
                try:
                    for wb in session['workbooks']:
                        for path_key in ['pdf_path', 'png_path', 'cropped_path']:
                            if path_key in wb and os.path.exists(wb[path_key]):
                                os.remove(wb[path_key])
                    if os.path.exists(output_path):
                        os.remove(output_path)
                except:
                    pass
            threading.Thread(target=delayed_cleanup).start()
        
        cleanup_after_download()
        
        return send_file(output_path, as_attachment=True, download_name=custom_filename)
        
    except Exception as e:
        logging.error(f"Error combining images: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download_result():
    if 'last_output' not in session:
        flash('No file to download', 'error')
        return redirect(url_for('index'))
    
    output_path = session['last_output']
    if not os.path.exists(output_path):
        flash('Output file not found', 'error')
        return redirect(url_for('index'))
    
    return send_file(output_path, as_attachment=True)

@app.route('/reset')
def reset():
    # Clean up any uploaded files
    if 'workbooks' in session:
        for wb in session['workbooks']:
            for path_key in ['pdf_path', 'png_path', 'cropped_path']:
                if path_key in wb and os.path.exists(wb[path_key]):
                    try:
                        os.remove(wb[path_key])
                    except:
                        pass
    
    # Clear session data except authentication
    keys_to_keep = ['tableau_token', 'tableau_site_id', 'tableau_user_id', 
                   'tableau_server', 'tableau_site', 'username']
    session_copy = {k: v for k, v in session.items() if k in keys_to_keep}
    session.clear()
    session.update(session_copy)
    
    flash('Reset complete', 'info')
    return redirect(url_for('index'))

@app.route('/image/<filename>')
def serve_image(filename):
    """Serve uploaded images"""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
