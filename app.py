import sqlite3
import os
from flask import Flask, render_template, request, url_for, redirect, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# --- CONFIGURATION & INITIALIZATION ---

# Define the path for the SQLite database
DATABASE = os.path.join(os.getcwd(), 'instance', 'book_recommender.db')

app = Flask(__name__)
# IMPORTANT: Use a secure secret key in production
app.config['SECRET_KEY'] = 'a_very_secret_key_for_recommendations'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Set the view function for login

# --- DATABASE UTILITIES ---

def get_db():
    """Connects to the specific database."""
    db = getattr(g, '_database', None)
    if db is None:
        # Check if the instance directory exists, create if not
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        db = g._database = sqlite3.connect(
            DATABASE,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        db.row_factory = sqlite3.Row # Allows accessing columns by name
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the database schema and populates sample data."""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # 1. Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
        ''')

        # 2. Books Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                genre TEXT NOT NULL,
                description TEXT
            );
        ''')

        # 3. Reviews Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                rating INTEGER NOT NULL, -- 1 to 5
                review_text TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (book_id) REFERENCES books (id),
                UNIQUE (user_id, book_id) -- Ensures one review per user per book
            );
        ''')

        # Populate sample books if none exist
        if db.execute('SELECT COUNT(*) FROM books').fetchone()[0] == 0:
            sample_books = [
                ('The Shadow of the Wind', 'Carlos Ruiz Zafón', 'Mystery', 'A magical tale set in a Barcelona book graveyard.'),
                ('The Martian', 'Andy Weir', 'Sci-Fi', 'An astronaut struggles to survive alone on Mars.'),
                ('A Gentleman in Moscow', 'Amor Towles', 'Historical Fiction', 'A count is sentenced to house arrest in a luxury hotel.'),
                ('Project Hail Mary', 'Andy Weir', 'Sci-Fi', 'A solitary survivor must save Earth from catastrophe.'),
                ('Where the Crawdads Sing', 'Delia Owens', 'Mystery', 'A story of a girl who raises herself in the marshes of North Carolina.'),
                ('Sapiens: A Brief History of Humankind', 'Yuval Noah Harari', 'Non-Fiction', 'A look at the history of humanity from early times to the present.'),
            ]
            cursor.executemany('''
                INSERT INTO books (title, author, genre, description) VALUES (?, ?, ?, ?)
            ''', sample_books)

        db.commit()

# Run the initialization only if the script is executed directly
if not os.path.exists(DATABASE):
    print("Initializing database and adding sample data...")
    init_db()

# --- USER MANAGEMENT (FLASK-LOGIN) ---

class User(UserMixin):
    """Class to manage authenticated user properties."""
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    """Required function for Flask-Login to load a user by ID."""
    db = get_db()
    user_data = db.execute('SELECT id, username FROM users WHERE id = ?', (user_id,)).fetchone()
    if user_data:
        return User(user_data['id'], user_data['username'])
    return None

# --- RECOMMENDATION LOGIC ---

def get_recommendations(user_id):
    """
    Generates recommendations based on the user's highly-rated genres
    (a simple content-based approach).
    """
    db = get_db()

    # 1. Find the genres the user rated highly (e.g., rating >= 4)
    # This query joins reviews and books to get the genre of highly-rated books.
    favorite_genres = db.execute('''
        SELECT b.genre
        FROM reviews r
        JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ? AND r.rating >= 4
        GROUP BY b.genre
        ORDER BY COUNT(b.genre) DESC
        LIMIT 3
    ''', (user_id,)).fetchall()

    if not favorite_genres:
        # If no high ratings, recommend the overall highest-rated books globally
        return db.execute('''
            SELECT b.*, AVG(r.rating) as avg_rating
            FROM books b
            LEFT JOIN reviews r ON b.id = r.book_id
            GROUP BY b.id
            ORDER BY avg_rating DESC
            LIMIT 5
        ''').fetchall()

    # Extract genre names
    genres = [g['genre'] for g in favorite_genres]

    # 2. Find unread/unreviewed books in those favorite genres
    # Use IN clause for the genres and check if the user has NOT reviewed the book.
    placeholders = ', '.join('?' for _ in genres)
    
    # Subquery to find all books the user has already reviewed
    reviewed_books = db.execute('SELECT book_id FROM reviews WHERE user_id = ?', (user_id,)).fetchall()
    reviewed_book_ids = [r['book_id'] for r in reviewed_books]
    
    # Build the main recommendation query
    recommendation_query = f'''
        SELECT b.*, AVG(r.rating) as avg_rating
        FROM books b
        LEFT JOIN reviews r ON b.id = r.book_id
        WHERE b.genre IN ({placeholders})
    '''
    
    # Add exclusion criteria for reviewed books
    if reviewed_book_ids:
        # Create placeholders for exclusion list
        exclusion_placeholders = ', '.join('?' for _ in reviewed_book_ids)
        recommendation_query += f' AND b.id NOT IN ({exclusion_placeholders})'
        params = tuple(genres) + tuple(reviewed_book_ids)
    else:
        params = tuple(genres)

    recommendation_query += '''
        GROUP BY b.id
        ORDER BY avg_rating DESC, b.title ASC
        LIMIT 5
    '''
    
    recommendations = db.execute(recommendation_query, params).fetchall()
    
    # Fallback: if no books match the favorite genres (e.g., all reviewed), return top global
    if not recommendations:
        return db.execute('''
            SELECT b.*, AVG(r.rating) as avg_rating
            FROM books b
            LEFT JOIN reviews r ON b.id = r.book_id
            WHERE b.id NOT IN ({exclusion_placeholders})
            GROUP BY b.id
            ORDER BY avg_rating DESC
            LIMIT 5
        ''').fetchall()


    return recommendations

# --- ROUTES ---

@app.route('/')
def index():
    """Displays the list of all books."""
    db = get_db()
    books = db.execute('''
        SELECT b.*, AVG(r.rating) as avg_rating, COUNT(r.id) as review_count
        FROM books b
        LEFT JOIN reviews r ON b.id = r.book_id
        GROUP BY b.id
        ORDER BY b.title ASC
    ''').fetchall()
    return render_template('index.html', books=books)

@app.route('/book/<int:book_id>', methods=['GET', 'POST'])
def book_detail(book_id):
    """Displays book detail and handles review submission."""
    db = get_db()
    book = db.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    
    if not book:
        flash('Book not found.', 'error')
        return redirect(url_for('index'))

    reviews = db.execute('''
        SELECT r.*, u.username
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.book_id = ?
        ORDER BY r.id DESC
    ''', (book_id,)).fetchall()

    user_review = None
    if current_user.is_authenticated:
        user_review = db.execute(
            'SELECT * FROM reviews WHERE user_id = ? AND book_id = ?',
            (current_user.id, book_id)
        ).fetchone()

    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('You must be logged in to submit a review.', 'warning')
            return redirect(url_for('login'))
        
        rating = request.form.get('rating', type=int)
        review_text = request.form.get('review_text')

        if not (1 <= rating <= 5):
            flash('Rating must be between 1 and 5.', 'error')
            return redirect(url_for('book_detail', book_id=book_id))

        try:
            if user_review:
                # Update existing review
                db.execute(
                    'UPDATE reviews SET rating = ?, review_text = ? WHERE id = ?',
                    (rating, review_text, user_review['id'])
                )
                flash('Your review has been updated!', 'success')
            else:
                # Insert new review
                db.execute(
                    'INSERT INTO reviews (user_id, book_id, rating, review_text) VALUES (?, ?, ?, ?)',
                    (current_user.id, book_id, rating, review_text)
                )
                flash('Your review has been submitted!', 'success')
            
            db.commit()
            return redirect(url_for('book_detail', book_id=book_id))

        except sqlite3.IntegrityError:
            flash('Error submitting review. You may have already reviewed this book.', 'error')
            return redirect(url_for('book_detail', book_id=book_id))
        except Exception as e:
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('book_detail', book_id=book_id))


    return render_template('book_detail.html', book=book, reviews=reviews, user_review=user_review)

@app.route('/recommendations')
@login_required
def recommendations():
    """Displays book recommendations for the logged-in user."""
    # current_user.id is available because of @login_required
    recommended_books = get_recommendations(current_user.id)
    return render_template('recommendations.html', recommended_books=recommended_books)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if user already exists
        if db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
            flash('Username already taken. Please choose a different one.', 'error')
        else:
            # Hash password and insert user
            password_hash = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                (username, password_hash)
            )
            db.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        
        user_data = db.execute(
            'SELECT id, username, password_hash FROM users WHERE username = ?', 
            (username,)
        ).fetchone()

        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(user_data['id'], user_data['username'])
            login_user(user)
            flash(f'Welcome back, {username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Handles user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Initial setup for sample data if run directly
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True)
