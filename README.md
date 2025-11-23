# Live Website at : 
https://ewaste-chatbot.onrender.com

# E-waste Image-based Chatbot (Flask + HTML/JS)

This is a template project for an e-waste assistant that:
- Accepts an image (upload or camera) from the user
- Uses a deep learning model to classify the product (Battery, Mobile, etc.)
- Provides clear disposal instructions
- Generates a link to the nearest e-waste recycling centres via Google Maps

## Folder Structure

    ewaste_chatbot_template/
    ├── backend/
    │   ├── app.py
    │   ├── model/
    │   │   ├── ewaste_model.h5          # (created after training)
    │   │   └── class_indices.json       # created/updated by training
    │   └── data/
    │       └── disposal_rules.json
    ├── frontend/
    │   ├── templates/
    │   │   └── index.html
    │   └── static/
    │       ├── script.js
    │       └── styles.css
    └── model_training/
        └── train_model.py

## How to Use

1. Create a folder `dataset/modified-dataset` in the project root and place your Kaggle dataset there,
   with `train/`, `val/`, and `test/` subfolders.

2. Create a virtual environment and install dependencies:

       python -m venv venv
       venv\Scripts\activate        # Windows
       # source venv/bin/activate     # Linux/Mac

       pip install -r requirements.txt

3. Train the model:

       cd model_training
       python train_model.py

   This will create `backend/model/ewaste_model.h5` and `backend/model/class_indices.json`.

4. Run the Flask app:

       cd ../backend
       python app.py

   Open http://127.0.0.1:5000/ in your browser.

5. From your phone or laptop, upload/capture an image of an e-waste item.
   The chatbot will show the predicted class, disposal steps and a link to nearby recycling centres.
