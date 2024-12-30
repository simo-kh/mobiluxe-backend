from flask import Flask, request, jsonify, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, jwt_required
from flask_cors import CORS  # Import CORS
import os, json, requests
from werkzeug.utils import secure_filename


app = Flask(__name__)
CORS(app, supports_credentials=True,resources={r"/*": {"origins": "*"}})


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app_new.db'
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['JWT_SECRET_KEY'] = 'supersecretjwtkey'
app.config['UPLOAD_FOLDER'] = 'uploads'  # Add upload folder configuration
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    image = db.Column(db.String(250), nullable=True)
    subcategories = db.relationship('Subcategory', backref='category', cascade='all, delete-orphan', lazy=True)

class Subcategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    image = db.Column(db.String(250), nullable=True)
    products = db.relationship('Product', backref='subcategory', cascade='all, delete-orphan', lazy=True)

from sqlalchemy import Enum

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    main_photo = db.Column(db.String(250), nullable=True)
    photos = db.Column(db.JSON, nullable=True)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)
    is_promotion = db.Column(db.Boolean, default=False)
    is_top_product = db.Column(db.Boolean, default=False)

    # Change from boolean to enum
    condition = db.Column(Enum(
        'Neuf',
        'D\'occasion - Comme neuf',
        'D\'occasion - Etat parfait',
        'D\'occasion - Très bon état',
        'D\'occasion - Bon état',
        'D\'occasion - Etat correct',
        name='product_condition'
    ), nullable=False, default='Neuf')

    stock = db.Column(db.Integer, nullable=False)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategory.id'), nullable=False)
    extra_attributes = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'main_photo': self.main_photo,
            'photos': self.photos,
            'description': self.description,
            'price': self.price,
            'original_price': self.original_price,
            'is_promotion': self.is_promotion,
            'is_top_product': self.is_top_product,
            'condition': self.condition,
            'stock': self.stock,
            'subcategory_id': self.subcategory_id,
            'extra_attributes': self.extra_attributes
        }



class Attribute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategory.id'), nullable=True)
    is_displayable = db.Column(db.Boolean, default=False)  # NEW FIELD

    category = db.relationship('Category', backref=db.backref('attributes', lazy=True))
    subcategory = db.relationship('Subcategory', backref=db.backref('attributes', lazy=True))

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and bcrypt.check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity={'username': user.username})
        return jsonify(access_token=access_token), 200
    return jsonify(message='Invalid credentials'), 401

@app.route('/categories', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    return jsonify([{'id': category.id, 'name': category.name, 'image': category.image.replace("localhost", "192.168.52.200")} for category in categories])

@app.route('/categories', methods=['POST'])
def add_category():
    data = request.get_json()
    print("Parsed data:", data)

    new_category = Category(name=data['name'], image=data['image'])
    db.session.add(new_category)
    db.session.commit()

    attributes = data.get('attributes', [])
    for attr in attributes:
        new_attribute = Attribute(
            name=attr['name'],
            category_id=new_category.id,
            is_displayable=attr.get('is_displayable', False)  # Add is_displayable
        )
        db.session.add(new_attribute)

    db.session.commit()
    return jsonify(message='Category added'), 201


@app.route('/categories/<int:id>', methods=['PUT', 'DELETE'])
def handle_single_category(id):
    category = Category.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.get_json()

        category.name = data['name']
        category.image = data['image']
        db.session.commit()

        # Get existing attributes
        existing_attributes = {attr.id: attr for attr in category.attributes}
        # Get IDs of incoming attributes
        incoming_ids = {attr['id'] for attr in data.get('attributes', []) if 'id' in attr}

        # Remove attributes not included in the update
        for attr_id in list(existing_attributes.keys()):
            if attr_id not in incoming_ids:
                db.session.delete(existing_attributes[attr_id])

        # Update or add attributes
        for attr in data.get('attributes', []):
            if 'id' in attr:
                attribute = Attribute.query.get(attr['id'])
                attribute.name = attr['name']
                attribute.is_displayable = attr.get('is_displayable', False)  # Update is_displayable
            else:
                new_attribute = Attribute(
                    name=attr['name'],
                    category_id=category.id,
                    is_displayable=attr.get('is_displayable', False)  # Add is_displayable
                )
                db.session.add(new_attribute)

        db.session.commit()
        return jsonify(message='Category updated'), 200

    elif request.method == 'DELETE':
        db.session.delete(category)
        db.session.commit()
        return jsonify(message='Category deleted'), 200



@app.route('/subcategories', methods=['GET'])
def get_subcategories():
    subcategories = Subcategory.query.all()

    return jsonify([{'id': subcategory.id, 'name': subcategory.name, 'category_id': subcategory.category_id, "image": subcategory.image} for subcategory in subcategories])

@app.route('/subcategories', methods=['POST'])
def add_subcategory():
    data = request.get_json()

    new_subcategory = Subcategory(
        name=data['name'], 
        category_id=data['category_id'], 
        image=data.get('image')  # Set the image URL if provided
    )
    db.session.add(new_subcategory)
    db.session.commit()

    # Handle attributes
    attributes = data.get('attributes', [])
    for attr in attributes:
        new_attribute = Attribute(
            name=attr['name'], 
            subcategory_id=new_subcategory.id,
            is_displayable=attr.get('is_displayable', False)  # Handle is_displayable
        )
        db.session.add(new_attribute)

    db.session.commit()
    return jsonify(message='Subcategory added'), 201


@app.route('/subcategories/<int:id>', methods=['PUT', 'DELETE'])
def handle_single_subcategory(id):
    subcategory = Subcategory.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.get_json()
        subcategory.name = data['name']
        subcategory.category_id = data['category_id']
        
        # Retain the existing image if not provided
        if 'image' in data and data['image']:
            subcategory.image = data['image']

        db.session.commit()

        # Update attributes
        existing_attributes = {attr.id: attr for attr in subcategory.attributes}
        incoming_ids = {attr['id'] for attr in data.get('attributes', []) if 'id' in attr}

        # Remove attributes not included in the update
        for attr_id in list(existing_attributes.keys()):
            if attr_id not in incoming_ids:
                db.session.delete(existing_attributes[attr_id])

        # Update or add attributes
        for attr in data.get('attributes', []):
            if 'id' in attr:
                attribute = Attribute.query.get(attr['id'])
                attribute.name = attr['name']
                attribute.is_displayable = attr.get('is_displayable', False)  # Update is_displayable
            else:
                new_attribute = Attribute(
                    name=attr['name'], 
                    subcategory_id=subcategory.id,
                    is_displayable=attr.get('is_displayable', False)  # Handle is_displayable
                )
                db.session.add(new_attribute)

        db.session.commit()
        return jsonify(message='Subcategory updated'), 200

    elif request.method == 'DELETE':
        db.session.delete(subcategory)
        db.session.commit()
        return jsonify(message='Subcategory deleted'), 200


@app.route('/attributes', methods=['GET'])
def get_attributes():
    subcategory_id = request.args.get('subcategory_id')
    category_id = request.args.get('category_id')

    attributes = []
    if subcategory_id:
        subcategory = Subcategory.query.get(subcategory_id)
        if not subcategory:
            return jsonify(message='Subcategory not found'), 404
        category_id = subcategory.category_id  # Get the category ID from the subcategory
        attributes.extend(subcategory.attributes)

    if category_id:
        category = Category.query.get(category_id)
        if not category:
            return jsonify(message='Category not found'), 404
        attributes.extend(category.attributes)

    response = [{
        'id': attribute.id,
        'name': attribute.name,
        'options': list(set(
            product.extra_attributes.get(attribute.name) 
            for product in Product.query.filter(
                (Product.subcategory_id == subcategory_id) | 
                (Product.subcategory.has(category_id=category_id))
            ).all() if attribute.name in product.extra_attributes))
    } for attribute in attributes]

    return jsonify(response)


@app.route('/products', methods=['GET'])
def get_products():
    subcategory_id = request.args.get('subcategory_id')
    category_id = request.args.get('category_id')
    filters = request.args.get('filters')
    price_min = request.args.get('price_min', 0, type=float)
    price_max = request.args.get('price_max', 200000, type=float)

    # Parse filters JSON if provided
    if filters:
        try:
            filters = json.loads(filters)
        except ValueError:
            filters = {}

    # Start building the query
    query = Product.query

    # Filter by subcategory_id if provided
    if subcategory_id:
        query = query.filter_by(subcategory_id=subcategory_id)

    # Filter by category_id if provided
    if category_id:
        query = query.filter(Product.subcategory.has(category_id=category_id))

    # Filter by price range
    query = query.filter(Product.price.between(price_min, price_max))

    # Apply extra filters
    if filters:
        # Filter by promotion if provided
        if 'is_promotion' in filters:
            query = query.filter(Product.is_promotion == (filters['is_promotion'].lower() == 'true'))

        # Filter by condition if provided
        if 'condition' in filters and filters['condition']:
            query = query.filter(Product.condition.in_(filters['condition']))

        # Apply filters on extra_attributes
        for key, values in filters.items():
            if key not in ['is_promotion', 'condition']:
                query = query.filter(Product.extra_attributes[key].astext.in_(values))

    # Fetch all matching products
    products = query.all()


    # Convert products to dictionaries and include `is_displayable` attributes
    processed_products = []
    for product in products:
        product_dict = product.to_dict()

        # Enhance extra_attributes with `is_displayable` if applicable
        if product.extra_attributes:
            enhanced_attributes = {}
            for key, value in product.extra_attributes.items():
                attribute = Attribute.query.filter_by(name=key).first()
                if attribute:
                    enhanced_attributes[key] = {
                        "value": value,
                        "is_displayable": attribute.is_displayable
                    }
            product_dict['extra_attributes'] = enhanced_attributes

        processed_products.append(product_dict)


    for product in processed_products:
        if product["main_photo"]:
            product["main_photo"] = product["main_photo"].replace("localhost", "192.168.52.200")
        if product["photos"]:
            product["photos"] = [
                photo.replace("localhost", "192.168.52.200") if isinstance(photo, str) else photo
                for photo in product["photos"]
            ]

    return jsonify(processed_products)


@app.route('/products', methods=['POST'])
def add_product():
    data = request.get_json()
    if 'subcategory_id' not in data:
        return jsonify(message='subcategory_id is required'), 400
    
    # Validate condition
    valid_conditions = [
        'Neuf',
        'D\'occasion - comme neuf',
        'D\'occasion - Etat parfait',
        'D\'occasion - Très bon état',
        'D\'occasion - Bon état',
        'D\'occasion - Etat correct'
    ]
    condition = data.get('condition', 'Neuf')
    if condition not in valid_conditions:
        return jsonify(message=f'Invalid condition. Must be one of: {", ".join(valid_conditions)}'), 400

    # Add product to the database
    new_product = Product(
        name=data['name'],
        main_photo=data.get('main_photo'),
        photos=data.get('photos'),
        description=data['description'],
        price=float(data['price']),
        original_price=float(data.get('original_price', 0)),
        is_promotion=data.get('is_promotion', False),
        is_top_product=data.get('is_top_product', False),
        condition=condition,
        stock=int(data['stock']),
        subcategory_id=data['subcategory_id'],
        extra_attributes=data.get('extra_attributes')
    )
    db.session.add(new_product)
    db.session.commit()
    return jsonify(message='Product added'), 201


@app.route('/products/<int:id>', methods=['PUT', 'DELETE'])
def handle_single_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.get_json()
        print(data)
        # Update fields that are provided in the request
        product.name = data['name']
        product.description = data['description']
        product.price = data['price']
        product.original_price = data['original_price']
        product.is_promotion = data.get('is_promotion', False)
        product.is_top_product = data.get('is_top_product', False)
        product.is_used = data.get('is_used', False)
        product.stock = data['stock']
        product.subcategory_id = data['subcategory_id']
        product.extra_attributes = data.get('extra_attributes', product.extra_attributes)
        product.condition = data['condition']

        # Retain existing photos if not provided in the update request
        if 'main_photo' in data and data['main_photo']:
            product.main_photo = data['main_photo']
        elif 'main_photo' not in data:
            product.main_photo = product.main_photo  # Keep the existing main photo

        if 'photos' in data and data['photos']:
            product.photos = data['photos']
        elif 'photos' not in data:
            product.photos = product.photos  # Keep the existing photos

        db.session.commit()
        return jsonify(message='Product updated'), 200

    elif request.method == 'DELETE':
        db.session.delete(product)
        db.session.commit()
        return jsonify(message='Product deleted'), 200


@app.route('/categories/<int:category_id>/attributes', methods=['GET'])
def get_category_attributes(category_id):
    attributes = Attribute.query.filter_by(category_id=category_id).all()
    return jsonify([{
        'id': attribute.id,
        'name': attribute.name,
        "is_displayable":attribute.is_displayable
    } for attribute in attributes])

@app.route('/categories/attributes', methods=['POST'])
def add_category_attribute():
    data = request.get_json()
    new_attribute = Attribute(
        name=data['name'],
        category_id=data['category_id']
    )
    db.session.add(new_attribute)
    db.session.commit()
    return jsonify(message='Category attribute added'), 201

@app.route('/subcategories/<int:subcategory_id>/attributes', methods=['GET'])
def get_subcategory_attributes(subcategory_id):
    attributes = Attribute.query.filter_by(subcategory_id=subcategory_id).all()
    return jsonify([{
        'id': attribute.id,
        'name': attribute.name,
        'is_displayable': attribute.is_displayable  # Include is_displayable
    } for attribute in attributes])


@app.route('/subcategories/attributes', methods=['POST'])
def add_subcategory_attribute():
    data = request.get_json()
    new_attribute = Attribute(
        name=data['name'],
        subcategory_id=data['subcategory_id']
    )
    db.session.add(new_attribute)
    db.session.commit()
    return jsonify(message='Subcategory attribute added'), 201

@app.route('/upload', methods=['POST'])
def upload():
    print(request.files)
    if 'image' not in request.files:
        return jsonify(message='No image file provided'), 400
    image = request.files['image']
    if image.filename == '':
        return jsonify(message='No selected file'), 400
    try:
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        image_url = url_for('uploaded_file', filename=filename, _external=True)
        return jsonify(url=image_url), 201
    except Exception as e:
        print(f'Error: {e}')
        return jsonify(message=str(e)), 422


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# Telegram Bot credentials
TELEGRAM_BOT_TOKEN = '7989611907:AAFYC1ufsixQyS9Ff6F6ovYPMei-kYSXMPw'  # Replace with your bot token
TELEGRAM_CHAT_ID = '5262780797'      # Replace with your chat ID

def send_telegram_notification(order_data):
    message = f"""
🛒 Nouvelle commande reçue:
📦 Produit: {order_data['productId']}
👤 Nom: {order_data['buyerName']}
📞 Téléphone: {order_data['buyerPhone']}
🏠 Adresse: {order_data['buyerAddress']}
🏙️ Ville: {order_data['buyerCity']}
💰 Prix: {order_data['price']} MAD
    """
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Telegram notification sent successfully.")
        else:
            print(f"Failed to send Telegram notification: {response.text}")
    except Exception as e:
        print(f"Error sending Telegram notification: {str(e)}")


@app.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json()
    try:
        # Simulate saving order to the database
        print(f"Order received: {data}")

        # Send Telegram notification
        send_telegram_notification(data)

        return jsonify(message="Order saved successfully"), 201
    except Exception as e:
        return jsonify(message="Failed to save order", error=str(e)), 500

from flask_migrate import Migrate

migrate = Migrate(app, db)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)