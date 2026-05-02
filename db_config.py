import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="your password",
    database="movie_db"
)