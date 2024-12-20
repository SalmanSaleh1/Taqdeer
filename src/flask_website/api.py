from flask import Flask, Blueprint, jsonify, request, render_template_string
from load_model import load_catboost_model
import numpy as np
import pandas as pd
from catboost import Pool
import db_connection
from db_classes import Property

# Initialize Blueprint
api_blueprint = Blueprint('api', __name__)

# Database connections
app = db_connection.app
db = db_connection.db
bcrypt = db_connection.bcrypt

# Load the CatBoost model
catboost_model = load_catboost_model()

# Define function for prediction (using the same formula as in your script)
def predict_property_value(area, city, district, Mukatat, space, property_classification, property_type, price_per_square_meter=None):
    # Prepare data dictionary for prediction
    data = {
        'area': [area],
        'city': [city],
        'district': [district],
        'Mukatat': [Mukatat],
        'property_classification': [property_classification],
        'property_type': [property_type],
        'space': [space],
        'log_space': [np.log1p(space)]  # Apply log(1 + space)
    }

    # If price_per_square_meter is provided, include it in the data dictionary
    if price_per_square_meter is not None:
        data['Price_per_square_meter'] = [price_per_square_meter]
    else:
        # If price_per_square_meter is not provided, set a default value (e.g., 0)
        data['Price_per_square_meter'] = [0]  # You can change this value if needed

    # Create DataFrame
    new_data = pd.DataFrame(data)

    # Rename columns to match the model's expected features
    new_data.rename(columns={
        'area': 'area',
        'city': 'city',
        'district': 'district',
        'Mukatat': 'Mukatat',
        'property_classification': 'property_classification',
        'property_type': 'property_type',
        'Price_per_square_meter': 'Price_per_square_meter',
        'space': 'space',
        'log_space': 'log_space'
    }, inplace=True)
    

    # Define categorical columns
    categorical_columns = ['area', 'city', 'district', 'Mukatat', 'property_classification', 'property_type', 'Price_per_square_meter']

    # Ensure categorical columns are strings
    for col in categorical_columns:
        new_data[col] = new_data[col].astype(str)

    # Ensure numerical columns are floats
    new_data['space'] = float(new_data['space'])
    new_data['log_space'] = np.log1p(new_data['space'])

    # Prepare data for CatBoost model
    input_pool = Pool(new_data, cat_features=categorical_columns)

    # Predict log price and convert it back
    log_price_pred = catboost_model.predict(input_pool)
    predicted_price = np.expm1(log_price_pred)  # Convert back from log scale

    return predicted_price[0]

# Prediction API endpoint
@api_blueprint.route('/predict/<int:object_id>', methods=['GET'])
def ml_api(object_id):
    property_info = get_info(object_id)
    if 'error' in property_info:
        return jsonify({"error": property_info['error']}), 404

    try:
        prediction = predict_property_value(
            area=property_info['area'],
            city=property_info['city'],
            district=property_info['district'],
            Mukatat=property_info['Mukatat'],
            space=float(property_info['space']),
            property_classification=property_info.get('property_classification', 'unknown'),
            property_type=property_info.get('property_type', 'unknown'),
            price_per_square_meter=property_info.get('price_per_square_meter', None)
        )
        return jsonify({"predicted_price": prediction})

    except Exception as e:
        return jsonify({"error": f"Model prediction failed: {e}"}), 500

# Database retrieval function (same as your previous version)
def get_info(object_id):
    try:
        property_details = Property.query.filter_by(id_object=object_id).first()
        if property_details:
            return {
                "area": property_details.area,
                "city": property_details.city_name,
                "district": property_details.district_name,
                "Mukatat": property_details.subdiv_no,
                "space": property_details.shape_area,
                "property_classification": property_details.parcel_land_use,
                "property_type": property_details.property_type,
                "price_per_square_meter": property_details.price_per_square_meter,
            }
        else:
            return {"error": "Property not found"}
    except Exception as e:
        return {"error": f"Error processing input: {e}"}

# Test endpoints
@api_blueprint.route('/test_prediction', methods=['GET'])
def test_prediction():
    try:
        predicted_price = predict_property_value(
            area="منطقة الرياض",
            city="الرياض",
            district="الزهرة",
            Mukatat="1017",
            property_classification="سكني",
            property_type="قطعة أرض",
            space=400.0,
            price_per_square_meter=163  # Add this line
        )
        return jsonify({"predicted_price": predicted_price})
    except Exception as e:
        return jsonify({"error": f"Test prediction failed: {str(e)}"}), 500

@api_blueprint.route('/estimate_price', methods=['POST'])
def estimate_price():
    try:
        # Get JSON data from the request
        data = request.get_json()
        
        # Extract parameters from JSON data
        area = data.get('area')
        city = data.get('city')
        district = data.get('district')
        Mukatat = data.get('mukatat')
        space = float(data.get('space', 0))
        property_classification = data.get('property_classification', 'unknown')
        property_type = data.get('property_type', 'unknown')
        
        # Call the prediction function
        predicted_price = predict_property_value(
            area=area,
            city=city,
            district=district,
            Mukatat=Mukatat,
            space=space,
            property_classification=property_classification,
            property_type=property_type
        )
        
        # Return the predicted price
        return jsonify({"predicted_price": predicted_price}), 200

    except Exception as e:
        # Log the error or print the full traceback
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500
        
# Register the blueprint with a URL prefix
app.register_blueprint(api_blueprint, url_prefix="/api")

if __name__ == "__main__":
    app.run(debug=True)
