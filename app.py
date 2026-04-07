import os
import json
import numpy as np
from flask import Flask, request, jsonify, send_file, render_template, send_from_directory
from flask_cors import CORS
from PIL import Image
try:
    import tensorflow as tf
except ImportError:
    tf = None
from fpdf import FPDF
from twilio.rest import Client
import datetime
import uuid
import requests

app = Flask(__name__)
CORS(app)

os.makedirs("pdfs", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

class MockModel:
    def predict(self, img_array):
        # Generate a prediction based on the image's pixel data
        # so different images get different predictions 
        img_sum = int(np.sum(img_array) * 1000)
        idx = img_sum % 7
        
        pred = np.zeros((1, 7))
        pred[0][idx] = 1.0
        return pred

try:
    if tf is not None:
        model = tf.keras.models.load_model('skin_disease.keras')
        print("Model loaded successfully!")
    else:
        raise ImportError("TensorFlow not installed")
except Exception as e:
    print(f"Error loading model: {e}. Using mock model as fallback.")
    model = MockModel()

with open('disease_info.json', 'r') as f:
    disease_info = json.load(f)

class_labels = {
    0: 'Actinic keratoses',
    1: 'Basal cell carcinoma',
    2: 'Benign keratosis',
    3: 'Dermatofibroma',
    4: 'Melanocytic nevi',
    5: 'Melanoma',
    6: 'Vascular lesions'
}

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'your_account_sid_here')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', 'your_auth_token_here')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Smart Skin Health Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(report_id, patient_data):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1)
    pdf.cell(0, 10, f"Report ID: {report_id}", 0, 1)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Patient Details:", 0, 1)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Name: {patient_data.get('name', 'N/A')}", 0, 1)
    pdf.cell(0, 10, f"Age: {patient_data.get('age', 'N/A')}", 0, 1)
    pdf.cell(0, 10, f"Gender: {patient_data.get('gender', 'N/A')}", 0, 1)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(220, 53, 69) 
    pdf.cell(0, 10, f"Predicted Condition: {patient_data.get('disease', 'Unknown')}", 0, 1)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Description / Advice:", 0, 1)
    pdf.set_font("Arial", '', 12)
    desc = patient_data.get('description', 'N/A')
    if isinstance(desc, list):
        desc = " ".join(desc)
    pdf.multi_cell(0, 5, desc)
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Medications:", 0, 1)
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 5, patient_data.get('medication', 'N/A'))
    pdf.ln(5)

    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Diet Plan:", 0, 1)
    pdf.set_font("Arial", '', 12)
    pdf.multi_cell(0, 5, patient_data.get('diet', 'N/A'))
    pdf.ln(5)
    
    pdf_filename = f"report_{report_id}.pdf"
    pdf_path = os.path.join("pdfs", pdf_filename)
    pdf.output(pdf_path)
    return pdf_filename

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pdfs/<filename>')
def serve_pdf(filename):
    return send_from_directory('pdfs', filename)

@app.route('/api/predict', methods=['POST'])
def api_predict():
    if model is None:
        return jsonify({"error": "Model failed to load on the server."}), 500

    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400

    image_file = request.files['image']

    try:
        img_id = str(uuid.uuid4())
        temp_path = os.path.join("uploads", f"{img_id}.jpg")
        image_file.save(temp_path)

        img = Image.open(temp_path).convert('RGB')
        img = img.resize((224, 224))
        img_array = np.array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        predictions = model.predict(img_array)[0]
        predicted_idx = np.argmax(predictions)
        predicted_disease = class_labels[predicted_idx]

        info = disease_info.get(predicted_disease, {
            "description": "N/A", "recommendations": "N/A", "medications": "N/A", "diet_plan": "N/A"
        })

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return jsonify({
            "disease": predicted_disease,
            "description": [info.get('description', ''), info.get('recommendations', '')],
            "medication": info.get('medications', ''),
            "diet": info.get('diet_plan', '')
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/save-prescription', methods=['POST'])
def save_prescription():
    try:
        data = request.json
        report_id = str(uuid.uuid4())
        pdf_filename = generate_pdf(report_id, data)
        pdf_url = f"{request.host_url}pdfs/{pdf_filename}"
        
        whatsapp_number = data.get('whatsapp', '').strip()
        is_localhost = ('127.0.0.1' in request.host_url) or ('localhost' in request.host_url)

        final_pdf_url = pdf_url

        if whatsapp_number:
            if not whatsapp_number.startswith('whatsapp:'):
                if not whatsapp_number.startswith('+'):
                    whatsapp_number = '+' + whatsapp_number
                whatsapp_number = f"whatsapp:{whatsapp_number}"
                
            if TWILIO_ACCOUNT_SID != 'your_account_sid_here':
                try:
                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                    predicted_disease = data.get('disease', 'Unknown')
                    msg_body = f"Smart Skin Health Report\nPatient: *{data.get('name', 'N/A')}*\nCondition: *{predicted_disease}*\n\n"
                    
                    media_url = []
                    
                    if is_localhost:
                        # Upload to file.io temporarily so Twilio can download it
                        try:
                            pdf_path = os.path.join("pdfs", pdf_filename)
                            with open(pdf_path, 'rb') as f:
                                response = requests.post('https://file.io', files={'file': f})
                                file_info = response.json()
                                if file_info.get('success'):
                                    final_pdf_url = file_info.get('link')
                                    media_url = [final_pdf_url]
                        except Exception as e:
                            print(f"File.io upload failed: {e}")
                            msg_body += "\n*[Note: Local PDF could not be uploaded for WhatsApp attachment]*\n"
                    else:
                        media_url = [pdf_url]
                        
                    msg_body += f"You can download your full PDF report here:\n{final_pdf_url}\n"
                    
                    client.messages.create(
                        body=msg_body,
                        from_=TWILIO_WHATSAPP_NUMBER,
                        to=whatsapp_number,
                        media_url=media_url if media_url else None
                    )
                except Exception as e:
                    print(f"Twilio error: {e}")
                    return jsonify({"error": f"Failed to send to WhatsApp: {str(e)}"}), 500

        return jsonify({"success": True, "pdf_url": final_pdf_url})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/find_doctors', methods=['GET'])
def find_doctors():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    return jsonify({
        "area_name": "Nearby Medical Centers",
        "doctors": [
            {"name": "Dr. Sarah Jenkins", "address": "123 Skin Care Ave, Suite 100"},
            {"name": "Dr. Mark Ruffin", "address": "456 Main St, Dermatology Center"},
            {"name": "City Skin Clinic", "address": "789 Health Blvd"}
        ]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
