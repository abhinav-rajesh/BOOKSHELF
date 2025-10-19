BookShelf AI: Personalized Book Recommendation System

Overview

BookShelf AI is a web application built with Flask and SQLite that allows users to register, log in, browse a catalog of books, submit reviews, and receive personalized book recommendations. The interface is styled with Tailwind CSS to resemble a modern, dark-themed streaming platform.

The core feature is a simple Content-Based Filtering recommendation engine that analyzes a user's high-rated books (4 and 5 stars) to identify their preferred genres and suggest new books accordingly.

Features

User Authentication: Secure registration and login using Flask-Login and werkzeug.security.

Database: Persistent data storage using a SQLite database.

Book Catalog: View all available books in a sleek, horizontally-scrolling "Trending Now" format.

Reviews: Users can submit, view, and edit their ratings and text reviews for any book.

Personalized Recommendations: Get book suggestions based on the genres of books you have rated highly.

Modern UI: Dark-themed, fully responsive interface using Tailwind CSS.

Getting Started

Prerequisites

You need Python 3.8+ installed on your system.

1. Installation

Install the required Python packages using pip:

pip install Flask Flask-Login Werkzeug


2. Project Structure

Ensure your project files are organized exactly as shown below:

book_recommender/
├── app.py                  # Main Flask application and logic
└── templates/              # HTML templates
    ├── base.html
    ├── index.html
    ├── register.html
    ├── login.html
    ├── book_detail.html
    └── recommendations.html
└── instance/               # (Folder is created before running)
    └── book_recommender.db # (Database file is generated on first run)


3. Running the Application

Navigate into your project directory (cd book_recommender).

Run the main application file:

python app.py


The console will show the local address where the application is running (e.g., http://127.0.0.1:5000/). Open this link in your web browser.

Note: The first time you run app.py, it automatically creates the book_recommender.db file, initializes the necessary tables (users, books, reviews), and populates the books table with sample data.

Technology Stack

Backend: Python (Flask)

Database: SQLite 3

Authentication: Flask-Login, Werkzeug

Frontend: HTML5, Jinja2 Templates, Tailwind CSS

Recommendation Logic Explained

The application uses a simple, yet effective, Content-Based Filtering approach:

When the user requests recommendations, the system fetches all reviews submitted by the current user.

It filters for books rated 4 stars or higher.

It determines the most common genres (up to 3) among those highly-rated books.

It then queries the books table for books that match those top genres and have not yet been reviewed by the user.

The final list is sorted by the book's overall average rating (global score).

This ensures the user sees highly-rated books in the genres they already love.
