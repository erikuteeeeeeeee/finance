import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
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

    #query database for username
    rows = db.execute("SELECT * FROM users WHERE id = :id",
                          id = session["user_id"])

    if rows == 0:
        return apology("missing user")

    #getting user's cash amount
    cash = rows[0]["cash"]

    #total = cash + value of stocks
    total = cash

    #query database for info about user's stocks
    stocks = db.execute("""SELECT symbol, SUM(shares) AS shares FROM transactions
                                WHERE user_id = :user_id GROUP BY symbol HAVING SUM(shares) > 0""", user_id = session["user_id"])

    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["name"] = quote["name"]
        stock["price"] = quote["price"]
        total += stock["shares"] * quote["price"]
        total_sm = stock["shares"] * quote["price"]


    return render_template("index.html", cash=cash, stocks=stocks, total=total, total_sm = total_sm)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        #checks for the symbol
        if not request.form.get("symbol"):
            return apology("symbol is missing")

        #check sif the symbol is valid
        quote = lookup(request.form.get("symbol").upper())
        if not quote:
            return apology("invalid symbol")

        shares = int(request.form.get("shares"))
        #print('step 1 | shares: ' + str(request.form.get("shares")), flush=True)

        #checks for the number of shares
        if not shares:
            return apology("missing number of shares")

        #checks if shares is a positive integer
        elif shares <= 0:
            return apology("posiive a integer required")

        #getting the price of shares
        price = quote["price"]
        #print('step 1 | price: ' + str(quote["price"]), flush=True)

        #getting cash of the user from database
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        cash = float(cash[0]["cash"])
        #print('step 1 | cash: ' + str(float(cash[0]["cash"])), flush=True)

        #checking if share is affordable for the user
        if cash < price * shares:
            return apology("can't afford")

        #updating cash owed after transaction
        else:
            updated_cash = cash - price * shares

        #updating amout of money in database
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                        cash = updated_cash,
                        id = session["user_id"])


        db.execute("INSERT INTO transactions(user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)",
                            user_id = session["user_id"],
                            symbol = quote["symbol"],
                            shares = shares,
                            price = quote["price"])

        flash("Bought!")
        return redirect("/")
    #if request.method == "GET"
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    #query database for username
    rows = db.execute("SELECT * FROM users WHERE id = :id",
                          id = session["user_id"])

    if rows == 0:
        return apology("missing user")

    #query database for info about user's stocks
    stocks = db.execute("""SELECT * FROM transactions WHERE user_id = :user_id """,
                                user_id = session["user_id"])

    for stock in stocks:
        quote = lookup(stock["symbol"])
        stock["price"] = quote["price"]



    return render_template("history.html", stocks=stocks)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                                username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        print('step 3 | user id: ' + str(session["user_id"]), flush=True)

        flash("Logged in!")
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

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("missing symbol")

        #get stock price
        quote = lookup(request.form.get("symbol").upper())

        if not quote:
            return apology("Invalid input.")

        return render_template("quoted.html", quote=quote)

    #if method is "GET"
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        #checks for username
        if not request.form.get("username"):
            return apology("Username is required.")

        #checks for password
        elif not request.form.get("password"):
            return apology("Pasword is required.")

        #checks for confirmation of the password
        elif not request.form.get("confirmation"):
            return apology("Confirm password.")

        # username check
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                                username=request.form.get("username"))

        # Ensure username does not exist
        if len(rows) != 0:
            return apology("this username is taken", 403)

        #check if password and confirmation are the same
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match")

        #inserts data into database
        db.execute("INSERT INTO users(username, hash) VALUES(:username, :hash)",
                        username = request.form.get("username"),
                        hash = generate_password_hash(request.form.get("password")))

        flash("Registered!")
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        symbol = request.form.get("symbol").upper()

        #checks for the symbol
        if not request.form.get("symbol"):
            return apology("symbol is missing")

        #check if the symbol is valid
        quote = lookup(request.form.get("symbol").upper())

        if not quote:
            return apology("invalid symbol")

        stock = db.execute("SELECT * FROM transactions WHERE user_id = :id AND symbol = :symbol",
                                id = session["user_id"],
                                symbol = quote["symbol"])

        #check if user owns the share
        if  len(stock) == 0:
            return apology("share not found")

        owned_shares = stock[0]["shares"]
        shares = int(request.form.get("shares"))

        #checks for the number of shares
        if not shares:
            return apology("missing number of shares")

        if shares > owned_shares:
            return apology("stock now owned")

        #getting the price of shares
        price = quote["price"]

        #getting cash of the user from database
        cash = db.execute("SELECT cash FROM users WHERE id = :id",
                                id = session["user_id"])
        cash = float(cash[0]["cash"])

        updated_cash = cash + shares * price

        #updating amout of money in database
        db.execute("UPDATE users SET cash = :cash WHERE id = :id",
                        cash = updated_cash,
                        id = session["user_id"])


        db.execute("INSERT INTO transactions(user_id, symbol, shares, price) VALUES(:user_id, :symbol, :shares, :price)",
                        user_id = session["user_id"],
                        symbol = quote["symbol"],
                        shares = -shares,
                        price = quote["price"])

        #update user's cash
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id",
                        cash = updated_cash,
                        user_id = session["user_id"])

        flash("Sold!")
        return redirect("/")
    #if request.method == "GET"
    else:

        #query database for info about user's stocks
        stocks = db.execute("""SELECT symbol, SUM(shares) AS shares FROM transactions
        WHERE user_id = :user_id GROUP BY symbol HAVING SUM(shares) > 0""", user_id = session["user_id"])

        for stock in stocks:
            quote = lookup(stock["symbol"])
            stock["symbol"] = quote["symbol"]

        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
