from flask import Flask, render_template, request, redirect, session
from db_config import db

app = Flask(__name__)
app.secret_key = "secret123"


# ---------------- LOGIN ----------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (request.form["username"], request.form["password"])
        )

        user = cursor.fetchone()
        cursor.close()

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/movies")

        return "Invalid login"

    return render_template("login.html")


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        cursor = db.cursor(buffered=True)

        cursor.execute(
            "INSERT INTO users (username, password, age) VALUES (%s, %s, %s)",
            (
                request.form["username"],
                request.form["password"],
                request.form["age"]
            )
        )

        db.commit()
        cursor.close()

        return redirect("/")

    return render_template("register.html")


# ---------------- MOVIES ----------------
@app.route("/movies")
def movies():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)

    try:
        page = int(request.args.get("page", 1))
    except:
        page = 1

    search = request.args.get("search", "")

    limit = 50
    offset = (page - 1) * limit

    query = """
        SELECT m.movie_id, m.title, m.genre, m.imdb_rating, m.year, r.rating
        FROM movies m
        LEFT JOIN ratings r
        ON m.movie_id = r.movie_id AND r.user_id = %s
    """

    params = [session["user_id"]]

    if search:
        query += " WHERE m.title LIKE %s"
        params.append(f"%{search}%")

    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    movies = cursor.fetchall()
    cursor.close()

    return render_template(
        "movies.html",
        movies=movies,
        page=page,
        search=search,
        watchlist_view=False
    )


# ---------------- RATE ----------------
@app.route("/rate", methods=["POST"])
def rate():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)

    cursor.execute("""
        INSERT INTO ratings (user_id, movie_id, rating)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE rating=%s
    """, (
        session["user_id"],
        request.form["movie_id"],
        request.form["rating"],
        request.form["rating"]
    ))

    db.commit()
    cursor.close()

    return redirect("/movies")

@app.route("/delete_rating", methods=["POST"])
def delete_rating():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)

    cursor.execute("""
        DELETE FROM ratings
        WHERE user_id=%s AND movie_id=%s
    """, (session["user_id"], request.form["movie_id"]))

    db.commit()
    cursor.close()

    return redirect("/movies")

@app.route("/recommend")
def recommend():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)
    user_id = session["user_id"]

    cursor.execute("""
        SELECT m.genre, AVG(r.rating)
        FROM ratings r
        JOIN movies m ON r.movie_id = m.movie_id
        WHERE r.user_id = %s
        GROUP BY m.genre
        ORDER BY AVG(r.rating) DESC
        LIMIT 2
    """, (user_id,))

    genres = cursor.fetchall()
    final_genres = [g[0] for g in genres]

    if final_genres:
        format_strings = ','.join(['%s'] * len(final_genres))

        query = f"""
            SELECT m.movie_id, m.title, m.genre, m.imdb_rating, m.year, r.rating
            FROM movies m
            LEFT JOIN ratings r
            ON m.movie_id = r.movie_id AND r.user_id = %s
            WHERE m.genre IN ({format_strings})
            ORDER BY m.imdb_rating DESC
            LIMIT 10
        """

        cursor.execute(query, (user_id, *final_genres))
    else:
        cursor.execute("""
            SELECT m.movie_id, m.title, m.genre, m.imdb_rating, m.year, r.rating
            FROM movies m
            LEFT JOIN ratings r
            ON m.movie_id = r.movie_id AND r.user_id = %s
            ORDER BY m.imdb_rating DESC
            LIMIT 10
        """, (user_id,))

    recs = cursor.fetchall()
    cursor.close()

    return render_template(
        "movies.html",
        movies=recs,
        page=1,
        search="",
        watchlist_view=False
    )


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)
    user_id = session["user_id"]

    # total + avg
    cursor.execute("""
        SELECT COUNT(*), AVG(rating)
        FROM ratings
        WHERE user_id=%s
    """, (user_id,))
    stats = cursor.fetchone()

    # favorite genre (FIXED)
    cursor.execute("""
        SELECT m.genre, AVG(r.rating) as avg_rating
        FROM ratings r
        JOIN movies m ON r.movie_id = m.movie_id
        WHERE r.user_id=%s
        GROUP BY m.genre
        ORDER BY avg_rating DESC
        LIMIT 1
    """, (user_id,))

    fav = cursor.fetchone()
    favorite_genre = fav[0] if fav else "Not enough data"

    # rated movies
    cursor.execute("""
        SELECT m.title, r.rating
        FROM ratings r
        JOIN movies m ON r.movie_id = m.movie_id
        WHERE r.user_id=%s
    """, (user_id,))

    rated_movies = cursor.fetchall()
    cursor.close()

    return render_template(
        "dashboard.html",
        total=stats[0],
        avg=round(stats[1], 2) if stats[1] else 0,
        genre=favorite_genre,
        rated_movies=rated_movies
    )


# ---------------- WATCHLIST ----------------
@app.route("/watchlist")
def watchlist():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)

    cursor.execute("""
        SELECT 
            m.movie_id, 
            m.title, 
            m.genre, 
            m.imdb_rating, 
            m.year,
            r.rating
        FROM movies m
        JOIN watchlist w ON m.movie_id = w.movie_id
        LEFT JOIN ratings r 
            ON m.movie_id = r.movie_id AND r.user_id = %s
        WHERE w.user_id = %s
    """, (session["user_id"], session["user_id"]))

    movies = cursor.fetchall()
    cursor.close()

    return render_template(
        "movies.html",
        movies=movies,
        page=1,
        search="",
        watchlist_view=True
    )


@app.route("/add_watchlist", methods=["POST"])
def add_watchlist():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)

    cursor.execute("""
        INSERT IGNORE INTO watchlist (user_id, movie_id)
        VALUES (%s, %s)
    """, (session["user_id"], request.form["movie_id"]))

    db.commit()
    cursor.close()

    return redirect("/movies")


@app.route("/remove_watchlist", methods=["POST"])
def remove_watchlist():
    if "user_id" not in session:
        return redirect("/")

    cursor = db.cursor(buffered=True)

    cursor.execute("""
        DELETE FROM watchlist
        WHERE user_id=%s AND movie_id=%s
    """, (session["user_id"], request.form["movie_id"]))

    db.commit()
    cursor.close()

    return redirect("/movies")


# ---------------- ADMIN ----------------
@app.route("/admin")
def admin():
    if session.get("username") != "admin":
        return "Access Denied"

    cursor = db.cursor(buffered=True)

    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()

    cursor.execute("SELECT * FROM movies")
    movies = cursor.fetchall()

    cursor.close()

    return render_template("admin.html", users=users, movies=movies)


@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):
    if session.get("username") != "admin":
        return "Access Denied"

    cursor = db.cursor(buffered=True)
    cursor.execute("DELETE FROM users WHERE user_id=%s", (user_id,))
    db.commit()
    cursor.close()

    return redirect("/admin")


@app.route("/delete_movie/<int:movie_id>")
def delete_movie(movie_id):
    if session.get("username") != "admin":
        return "Access Denied"

    cursor = db.cursor(buffered=True)
    cursor.execute("DELETE FROM movies WHERE movie_id=%s", (movie_id,))
    db.commit()
    cursor.close()

    return redirect("/admin")


app.run(debug=True)