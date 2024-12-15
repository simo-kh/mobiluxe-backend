from flask import Flask, request, jsonify, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_cors import CORS  # Import CORS
import os, json
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
    products = db.relationship('Product', backref='subcategory', cascade='all, delete-orphan', lazy=True)

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
    is_used = db.Column(db.Boolean, default=False)
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
            'is_used': self.is_used,
            'stock': self.stock,
            'subcategory_id': self.subcategory_id,
            'extra_attributes': self.extra_attributes
        }


class Attribute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategory.id'), nullable=True)
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
    return jsonify([{'id': category.id, 'name': category.name, 'image': category.image} for category in categories])

@app.route('/categories', methods=['POST'])
@jwt_required()
def add_category():
    data = request.get_json()
    new_category = Category(name=data['name'], image=data['image'])
    db.session.add(new_category)
    db.session.commit()

    attributes = data.get('attributes', [])
    for attr in attributes:
        new_attribute = Attribute(name=attr['name'], category_id=new_category.id)
        db.session.add(new_attribute)

    db.session.commit()
    return jsonify(message='Category added'), 201

@app.route('/categories/<int:id>', methods=['PUT', 'DELETE'])
@jwt_required()
def handle_single_category(id):
    category = Category.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.get_json()
        category.name = data['name']
        category.image = data['image']
        db.session.commit()

        attributes = data.get('attributes', [])
        for attr in attributes:
            if 'id' in attr:
                attribute = Attribute.query.get(attr['id'])
                attribute.name = attr['name']
            else:
                new_attribute = Attribute(name=attr['name'], category_id=category.id)
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
    return jsonify([{'id': subcategory.id, 'name': subcategory.name, 'category_id': subcategory.category_id} for subcategory in subcategories])

@app.route('/subcategories', methods=['POST'])
@jwt_required()
def add_subcategory():
    data = request.get_json()
    new_subcategory = Subcategory(name=data['name'], category_id=data['category_id'])
    db.session.add(new_subcategory)
    db.session.commit()

    # Handle attributes
    attributes = data.get('attributes', [])
    for attr in attributes:
        new_attribute = Attribute(name=attr['name'], subcategory_id=new_subcategory.id)
        db.session.add(new_attribute)

    db.session.commit()
    return jsonify(message='Subcategory added'), 201

@app.route('/subcategories/<int:id>', methods=['PUT', 'DELETE'])
@jwt_required()
def handle_single_subcategory(id):
    subcategory = Subcategory.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.get_json()
        subcategory.name = data['name']
        subcategory.category_id = data['category_id']
        db.session.commit()

        # Update attributes
        attributes = data.get('attributes', [])
        for attr in attributes:
            if 'id' in attr:
                attribute = Attribute.query.get(attr['id'])
                attribute.name = attr['name']
            else:
                new_attribute = Attribute(name=attr['name'], subcategory_id=subcategory.id)
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
    filters = request.args.get('filters')
    price_min = request.args.get('price_min', 0, type=float)
    price_max = request.args.get('price_max', 10000, type=float)

    if filters:
        try:
            filters = json.loads(filters)
        except ValueError:
            filters = {}

    query = Product.query

    if subcategory_id:
        query = query.filter_by(subcategory_id=subcategory_id)

    query = query.filter(Product.price.between(price_min, price_max))

    if filters:
        # Apply promotion and used filters
        if filters.get('is_promotion'):
            query = query.filter(Product.is_promotion == True if 'true' in filters['is_promotion'] else Product.is_promotion == False)
        if filters.get('is_used'):
            query = query.filter(Product.is_used == True if 'true' in filters['is_used'] else Product.is_used == False)

    initial_products = query.all()
    print("Initial products:", [product.to_dict() for product in initial_products])

    # Apply extra attributes filters
    if filters:
        filtered_products = []
        for product in initial_products:
            match = True
            for key, values in filters.items():
                if key not in ['is_promotion', 'is_used']:
                    if values:
                        attribute_value = product.extra_attributes.get(key)
                        if attribute_value not in values:
                            match = False
                            break
            if match:
                filtered_products.append(product)
    else:
        filtered_products = initial_products

    result = [product.to_dict() for product in filtered_products]
    print("Filtered result:", result)
    return jsonify(result)



@app.route('/products', methods=['POST'])
@jwt_required()
def add_product():
    data = request.get_json()
    if 'subcategory_id' not in data:
        return jsonify(message='subcategory_id is required'), 400
    
    # Convert empty strings to None for numeric fields
    price = float(data['price']) if data.get('price') else None
    original_price = float(data['original_price']) if data.get('original_price') else None
    
    print(data)
    new_product = Product(
        name=data['name'],
        main_photo=data.get('main_photo'),
        photos=data.get('photos'),
        description=data['description'],
        price=price,
        original_price=original_price,
        is_promotion=data.get('is_promotion', False),
        is_top_product=data.get('is_top_product', False),
        is_used=data.get('is_used', False),
        stock=int(data['stock']) if data.get('stock') else 0,
        subcategory_id=data['subcategory_id'],
        extra_attributes=data.get('extra_attributes')
    )
    db.session.add(new_product)
    db.session.commit()
    return jsonify(message='Product added'), 201


@app.route('/products/<int:id>', methods=['PUT', 'DELETE'])
@jwt_required()
def handle_single_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.get_json()
        product.name = data['name']
        product.main_photo = data.get('main_photo')
        product.photos = data.get('photos')
        product.description = data['description']
        product.price = data['price']
        product.original_price = data.get('original_price')
        product.is_promotion = data.get('is_promotion', False)
        product.is_used = data.get('is_used', False)  # Remove the comma here
        product.is_top_product = data.get('is_top_product', False)
        product.stock = data['stock']
        product.subcategory_id = data['subcategory_id']
        product.extra_attributes = data.get('extra_attributes')
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
        'name': attribute.name
    } for attribute in attributes])

@app.route('/categories/attributes', methods=['POST'])
@jwt_required()
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
        'name': attribute.name
    } for attribute in attributes])

@app.route('/subcategories/attributes', methods=['POST'])
@jwt_required()
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
@jwt_required()
def upload():
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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
