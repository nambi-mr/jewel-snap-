import os
import csv
import io
from flask import Flask, request, render_template, redirect, url_for, flash, send_file, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# --- App Initialization and Configuration ---
app = Flask(__name__, static_folder='uploads')
app.secret_key = 'a_very_secret_random_key_for_session_management'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- புதிய மாற்றம்: எல்லா தயாரிப்பு வகைகளின் நிலையான பட்டியல் ---
ALL_PRODUCT_CATEGORIES = [
    'necklace', 'oriana necklace', 'vintage and ethinic', 'thirumangalyam', 'chain', 
    'short chain', 'long chain', 'bb chain', 'double row', 'mugappu chain', 
    'rings', 'wedding ring', 'earrings', 'stud', 'jimikki', 'drops', 'dollar', 
    'bangle', 'single bangle', 'baby products', '18kt product', 'order product'
]

# --- User Login Configuration ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

users = {
    'coimbatore': {'password': generate_password_hash('cbe@123'), 'branch_name': 'Coimbatore'},
    'madurai': {'password': generate_password_hash('mdu@456'), 'branch_name': 'Madurai'},
    'chennai': {'password': generate_password_hash('chn@789'), 'branch_name': 'Chennai'}
}

class User(UserMixin):
    def __init__(self, id, branch_name):
        self.id = id
        self.branch_name = branch_name

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(id=user_id, branch_name=users[user_id]['branch_name'])
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- WEB PAGE ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username]['password'], password):
            user = User(id=username, branch_name=users[username]['branch_name'])
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'product_image' not in request.files:
        flash('No file part in the request!', 'error')
        return redirect(request.url)
    file = request.files['product_image']
    if file.filename == '':
        flash('No selected file!', 'error')
        return redirect(request.url)
    product_name = request.form['product_name']
    if file and allowed_file(file.filename):
        branch_name = current_user.branch_name
        target_folder = os.path.join(app.config['UPLOAD_FOLDER'], branch_name, product_name)
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        filename = secure_filename(file.filename)
        file.save(os.path.join(target_folder, filename))
        product_code = request.form['product_code']
        weight_band = request.form['weight_band']
        with open('database.csv', 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(['branch', 'image_path', 'product_name', 'product_code', 'weight_band'])
            image_db_path = os.path.join(branch_name, product_name, filename).replace("\\", "/")
            writer.writerow([branch_name, image_db_path, product_name, product_code, weight_band])
        flash(f'Product "{product_name}" saved successfully!', 'success')
        return redirect(url_for('index'))
    else:
        flash('Invalid file type!', 'error')
        return redirect(request.url)

# --- இதுதான் மாற்றப்பட்ட கேலரி ஃபங்ஷன் ---
@app.route('/gallery')
@login_required
def gallery():
    """Shows a predefined list of all product category folders."""
    return render_template('gallery.html', folders=ALL_PRODUCT_CATEGORIES, branch_name=current_user.branch_name)

@app.route('/gallery/<folder_name>')
@login_required
def view_folder(folder_name):
    products_in_folder = []
    branch_name = current_user.branch_name
    try:
        with open('database.csv', 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['branch'] == branch_name and row['product_name'] == folder_name:
                    products_in_folder.append(row)
    except FileNotFoundError:
        pass
    return render_template('folder_view.html', products=products_in_folder, folder_name=folder_name)

@app.route('/generate_selected_pdf', methods=['POST'])
@login_required
def generate_selected_pdf():
    selected_codes = request.form.getlist('selected_products')
    if not selected_codes:
        flash('You did not select any products.', 'error')
        return redirect(url_for('gallery'))
    all_products = []
    try:
        with open('database.csv', 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            all_products = list(reader)
    except FileNotFoundError:
        return "Database not found."
    products_to_print = [p for p in all_products if p['product_code'] in selected_codes and p['branch'] == current_user.branch_name]
    
    # ... மீதமுள்ள PDF லாஜிக் அப்படியே இருக்கும் ...
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    SMALL_PRODUCTS = ['earrings', 'rings', 'drops', 'dollar', 'jimikki', 'thirumangalyam', 'wedding ring', 'mattal', 'bracelet', 'baby product', 'stud']
    SMALL_IMG_WIDTH, SMALL_IMG_HEIGHT = 2.19 * inch, 1.92 * inch
    LARGE_IMG_WIDTH, LARGE_IMG_HEIGHT = 5.86 * inch, 8.07 * inch
    def draw_small_products_table(products):
        table_data = []
        row = []
        for product in products:
            try:
                img = Image(os.path.join(app.config['UPLOAD_FOLDER'], product['image_path']), width=SMALL_IMG_WIDTH, height=SMALL_IMG_HEIGHT)
            except Exception:
                img = Paragraph(f"Image not found", styles['Normal'])
            details = f"<b>Code:</b> {product['product_code']}<br/><b>Name:</b> {product['product_name']}<br/><b>Weight:</b> {product['weight_band']}"
            p = Paragraph(details, styles['Normal'])
            cell_content = [img, Spacer(1, 0.1*inch), p]
            row.append(cell_content)
            if len(row) == 3: table_data.append(row); row = []
        if row: table_data.append(row)
        table = Table(table_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
        table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey)]))
        return table
    small_products_buffer = []
    for product in products_to_print:
        product_name = product['product_name'].lower()
        if product_name in SMALL_PRODUCTS:
            small_products_buffer.append(product)
            if len(small_products_buffer) == 9: story.append(draw_small_products_table(small_products_buffer)); story.append(PageBreak()); small_products_buffer = []
        else:
            if small_products_buffer: story.append(draw_small_products_table(small_products_buffer)); story.append(PageBreak()); small_products_buffer = []
            try:
                img = Image(os.path.join(app.config['UPLOAD_FOLDER'], product['image_path']), width=LARGE_IMG_WIDTH, height=LARGE_IMG_HEIGHT)
            except Exception:
                img = Paragraph(f"Image not found", styles['Normal'])
            story.append(img)
            details = f"<para align=center><b>Code:</b> {product['product_code']} | <b>Name:</b> {product['product_name']} | <b>Weight:</b> {product['weight_band']}</para>"
            story.append(Paragraph(details, styles['Normal']))
            story.append(PageBreak())
    if small_products_buffer: story.append(draw_small_products_table(small_products_buffer))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='selected_products.pdf', mimetype='application/pdf')

# manifest.json கோப்பிற்கான ரூட்
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(app.root_path, 'manifest.json')
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)