from flask import Blueprint, jsonify, request

account_bp = Blueprint('account', __name__)

# Dummy in-memory user store for demo
users = {}
saved_routes = {}

@account_bp.route('/api/account/create', methods=['POST'])
def create_account():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    name = data.get('name')
    if not email or not password or not name:
        return jsonify({'error': 'Missing fields'}), 400
    if email in users:
        return jsonify({'error': 'Account already exists'}), 409
    users[email] = {'email': email, 'password': password, 'name': name}
    saved_routes[email] = []
    return jsonify({'message': 'Account created', 'user': users[email]})

@account_bp.route('/api/account/delete', methods=['POST'])
def delete_account():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    if email not in users or users[email]['password'] != password:
        return jsonify({'error': 'Invalid credentials'}), 401
    del users[email]
    del saved_routes[email]
    return jsonify({'message': 'Account deleted'})

@account_bp.route('/api/account/update', methods=['POST'])
def update_account():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    new_password = data.get('new_password')
    if email not in users or users[email]['password'] != password:
        return jsonify({'error': 'Invalid credentials'}), 401
    users[email]['password'] = new_password
    return jsonify({'message': 'Password updated'})

@account_bp.route('/api/account/save_route', methods=['POST'])
def save_route():
    data = request.json
    email = data.get('email')
    route = data.get('route')
    if email not in users:
        return jsonify({'error': 'Invalid user'}), 401
    saved_routes[email].append(route)
    return jsonify({'message': 'Route saved', 'routes': saved_routes[email]})

@account_bp.route('/api/account/routes', methods=['GET'])
def get_routes():
    email = request.args.get('email')
    if email not in users:
        return jsonify({'error': 'Invalid user'}), 401
    return jsonify({'routes': saved_routes[email]})
