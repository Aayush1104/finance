import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = session["user_id"]
    
    stocks = db.execute(
        "SELECT symbol, name, price, SUM(shares) as wholeshares FROM transactions WHERE user_id = ? GROUP BY symbol", user)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user)[0]["cash"]
    
    total = cash
    
    for bruh in stocks:
        total += bruh["price"] * bruh["wholeshares"]
    
    return render_template("index.html", stocks=stocks, cash=usd(cash), total=usd(total), usd=usd)
    
    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        shares = request.form.get("shares")
        if not symbol:
            return apology("Input a valid symbol")
        elif not stock:
            return apology("Input a valid symbol")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("Input a valid integer")
        if not shares:
            return apology("Input how many shares")
        elif shares <= 0:
            return apology("Positive shares please")
        
        user = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user)[0]["cash"]
        
        stockname = stock["name"]
        stockprice = stock["price"]
        wholeprice = stockprice * shares
        symbol = symbol.upper()
        if wholeprice > cash:
            return apology("You too poor lol")
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - wholeprice, user)
            db.execute("INSERT INTO transactions (user_id, name, symbol, shares, type, price) VALUES(?, ?, ?, ?, ?, ?)",
                       user, stockname, symbol, shares, "buy", stockprice)
        return redirect("/")
    else:
        return render_template("buy.html")  # TODO


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    history = db.execute("SELECT type, symbol, price, shares, time FROM transactions WHERE user_id = ?", user)
    return render_template("history.html", history=history)
    

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
        
    elif request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Enter a Symbol")
        stock = lookup(symbol)
        if not stock:
            return apology("Invalid symbol")
        return render_template("quoted.html", stock=stock, usd_function=usd)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        verify = request.form.get("confirmation")
        if not username:
            return apology("Input a username")
        elif not password:
            return apology("Input a password")
        elif not verify:
            return apology("Input your password again")
        elif verify != password:
            return apology("Passwords don't match :(")
        hash = generate_password_hash(password)
        try:
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
            
            return redirect("/")
        except:
            return apology("Username taken")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        
        if shares <= 0:
            return apology("Shares must be a positive integer")
        stockprice = lookup(symbol)["price"]
        stockname = lookup(symbol)["name"]
        holdings = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user, symbol)[
            0]["shares"]
        if shares > holdings:
            return apology("You too poor in shares lol")
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user)[0]["cash"]
        earnings = shares * stockprice
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + earnings, user)
        db.execute("INSERT INTO transactions (user_id, name, symbol, shares, type, price) VALUES(?, ?, ?, ?, ?, ?)",
                   user, stockname, symbol, -shares, "sell", stockprice)
        return redirect("/")
    else:
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user)  # TODO
        return render_template("sell.html", symbols=symbols)
        

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
