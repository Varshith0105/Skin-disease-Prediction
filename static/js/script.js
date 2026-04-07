document.addEventListener('DOMContentLoaded', () => {
    const uploadArea = document.getElementById('upload-area');
    const imageInput = document.getElementById('image-input');
    const imagePreview = document.getElementById('image-preview');
    const fileInfo = document.getElementById('file-info');
    const uploadPrompt = document.querySelector('.upload-prompt');
    const form = document.getElementById('prediction-form');
    
    // UI Elements for state
    const submitBtn = document.getElementById('submit-btn');
    const loadingState = document.getElementById('loading-state');
    const resultsArea = document.getElementById('results-area');

    // Drag and drop setup
    uploadArea.addEventListener('click', () => imageInput.click());
    
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            imageInput.files = e.dataTransfer.files;
            handleFile(e.dataTransfer.files[0]);
        }
    });

    imageInput.addEventListener('change', function() {
        if (this.files && this.files[0]) {
            handleFile(this.files[0]);
        }
    });

    function handleFile(file) {
        if (!file.type.match('image.*')) {
            alert('Please select an image file');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            imagePreview.style.display = 'block';
            uploadPrompt.style.display = 'none';
            fileInfo.textContent = file.name;
        };
        reader.readAsDataURL(file);
        
        // Reset results area if new image is uploaded
        resultsArea.style.display = 'none';
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        if (!imageInput.files || !imageInput.files[0]) {
            alert("Please upload an image first.");
            return;
        }

        const formData = new FormData();
        formData.append('image', imageInput.files[0]);
        
        const whatsappNumber = document.getElementById('whatsapp-number').value;
        if(whatsappNumber) {
            formData.append('whatsapp_number', whatsappNumber);
        }

        // UI updates
        form.style.display = 'none';
        loadingState.style.display = 'block';
        resultsArea.style.display = 'none';

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.error) {
                alert(`Error: ${data.error}`);
                form.style.display = 'block';
                return;
            }

            // Populate Results
            document.getElementById('disease-badge').textContent = data.disease;
            document.getElementById('res-description').textContent = data.info.description;
            document.getElementById('res-recommendations').textContent = data.info.recommendations;
            document.getElementById('res-medications').textContent = data.info.medications;
            document.getElementById('res-diet').textContent = data.info.diet_plan;
            
            document.getElementById('download-pdf-btn').href = data.pdf_url;

            const whatsappStatus = document.getElementById('whatsapp-status');
            whatsappStatus.innerHTML = `<i class="fa-solid fa-circle-info"></i> WhatsApp Status: ${data.message_status}`;

            // Show results
            loadingState.style.display = 'none';
            resultsArea.style.display = 'block';
            
        } catch (error) {
            console.error(error);
            alert("An error occurred while connecting to the server.");
        } finally {
            // Restore form visibility for new uploads
            form.style.display = 'block';
            loadingState.style.display = 'none';
        }
    });
});
