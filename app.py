from flask import Flask, render_template
from flask_socketio import SocketIO, send, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app)

# Database model for messages
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    content = db.Column(db.String(200), nullable=False)
    room = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message {self.id} - {self.username}: {self.content} in {self.room}>'

# Database model for rooms
class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f'<Room {self.name}>'

@app.route('/')
def index():
    return render_template('index.html')

# Handle room creation and ensure it is stored in the database
@socketio.on('create_room')
def create_room(room_name):
    if not Room.query.filter_by(name=room_name).first():
        new_room = Room(name=room_name)
        db.session.add(new_room)
        db.session.commit()

    available_rooms = [room.name for room in Room.query.all()]
    socketio.emit('room_list', available_rooms)

# Send the list of rooms to a client when requested
@socketio.on('get_rooms')
def get_rooms():
    available_rooms = [room.name for room in Room.query.all()]
    socketio.emit('room_list', available_rooms)

# Load chat history when a user joins a room
@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    
    # Send system message that the user has joined
    send({'username': 'System', 'content': f'{username} has entered the room.'}, to=room)
    
    # Fetch and send chat history for the room
    previous_messages = Message.query.filter_by(room=room).order_by(Message.timestamp.asc()).all()
    for msg in previous_messages:
        send({'username': msg.username, 'content': msg.content, 'timestamp': msg.timestamp.strftime('%Y-%m-%d %H:%M:%S')}, to=username)

# Event listener for messages, now storing them in the database
@socketio.on('message')
def handle_message(data):
    print(f'Message from {data["username"]} in room {data["room"]}: {data["content"]}')
    
    # Save the message to the database
    new_message = Message(username=data['username'], content=data['content'], room=data['room'])
    db.session.add(new_message)
    db.session.commit()

    # Broadcast the message to the specific room
    send({'username': data['username'], 'content': data['content'], 'timestamp': new_message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}, to=data['room'])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    socketio.run(app, debug=True)
