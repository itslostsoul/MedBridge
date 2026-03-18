from flask import Flask, render_template, request, redirect, session, url_for, flash, send_file
from flask_mysqldb import MySQL
from datetime import datetime, timedelta
import io
import qrcode

app = Flask(__name__)

app.secret_key = 'mindflayers_secret_key'
app.config['MYSQL_HOST'] = 'mysql-15e12385-nimalyd20-bfe1.j.aivencloud.com'
app.config['MYSQL_PORT'] = 16657
app.config['MYSQL_USER'] = 'avnadmin'
app.config['MYSQL_PASSWORD'] = 'AVNS_akVQBE4Ujva0j3Kbjw4'
app.config['MYSQL_DB'] = 'defaultdb'

mysql = MySQL(app)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM users WHERE email= %s AND password= %s', (email, password))
        account = cur.fetchone()
        if account:
            session['loggedin'] = True
            session['user_id'] = account[0]
            session['role'] = account[4]
            return redirect(url_for('dashboard'))
        else:
            msg = 'Incorrect email or password'
    return render_template('login.html', msg=msg)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = ''
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        account = cur.fetchone()
        
        if account:
            msg = "Account already exists! Please use a different email."
            return render_template('register.html', msg=msg)

        if password != confirm_password:
            msg = "Passwords do not match!"
            return render_template('register.html', msg=msg)
        
        cur.execute('INSERT INTO users (full_name, email, password, role) VALUES(%s, %s, %s, %s)', (full_name, email, password, role))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('login'))
        
    return render_template('register.html', msg=msg)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    view = request.args.get('view', 'listings')
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    if session['role'] == 'donor':
        cur.execute("SELECT impact_points FROM users WHERE id = %s", [user_id])
        points_data = cur.fetchone()
        points = points_data[0] if points_data else 0
        my_meds, pickups, messages = [], [], []
        if view == 'listings':
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute("""
                SELECT * FROM medications 
                WHERE donor_id = %s 
                AND status = 'available' 
                AND expiry_time > %s
            """, (user_id, now))
            my_meds = cur.fetchall()
        elif view == 'pickups':
            cur.execute("""
                SELECT m.name, m.quantity, u.full_name, c.claim_date
                FROM medications m
                JOIN claims c ON m.id = c.med_id
                JOIN users u ON c.recipient_id = u.id
                WHERE m.donor_id = %s AND m.status = 'delivered'
            """, [user_id])
            pickups = cur.fetchall()
        elif view == 'feedback':
            cur.execute("""
                SELECT m.name, u.full_name, fb.message, fb.type, fb.created_at
                FROM feedback fb
                JOIN medications m ON fb.med_id = m.id
                JOIN users u ON fb.recipient_id = u.id
                WHERE fb.donor_id = %s
                ORDER BY fb.created_at DESC
            """, [user_id])
            messages = cur.fetchall()

        cur.close()
        return render_template('donor_dashboard.html', points=points, food=my_meds, 
                               pickups=pickups, messages=messages, current_view=view)

    else:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("""
            SELECT * FROM medications 
            WHERE status = 'available' 
            AND expiry_time > %s
        """, [now])
        available_meds = cur.fetchall()
        cur.close()
        return render_template('recipient_dashboard.html', food=available_meds)

@app.route('/post_med', methods=['POST'])
def post_med():
    if session.get('role') == 'donor':
        med_name = request.form['med_name']
        quantity = request.form['quantity']
        donor_id = session['user_id']
        expiry_raw = request.form['expiry'] 
        expiry_time = expiry_raw.replace('T', ' ') + ':00'
        
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO medications (donor_id, name, quantity, expiry_time) VALUES (%s, %s, %s, %s)", (donor_id, med_name, quantity, expiry_time))
        cur.execute("UPDATE users SET impact_points = impact_points + 10 WHERE id = %s", [donor_id])
        mysql.connection.commit()
        cur.close()
    return redirect(url_for('dashboard'))

@app.route('/claim_med/<int:med_id>')
def claim_med(med_id):
    if session.get('role') == 'recipient':
        recipient_id = session['user_id']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE medications SET status = 'claimed' WHERE id = %s AND status = 'available'", [med_id])
        if cur.rowcount > 0:
            cur.execute("INSERT INTO claims (med_id, recipient_id) VALUES (%s, %s)", (med_id, recipient_id))
            mysql.connection.commit()
        cur.close()
    return render_template('claim_success.html', med_id=med_id)

@app.route('/cancel_claim/<int:med_id>')
def cancel_claim(med_id):
    if 'user_id' not in session or session.get('role') != 'recipient':
        return redirect(url_for('login'))
    
    recipient_id = session['user_id']
    cur = mysql.connection.cursor()

    cur.execute("SELECT id FROM claims WHERE med_id = %s AND recipient_id = %s", (med_id, recipient_id))
    claim = cur.fetchone()

    if claim:
        cur.execute("UPDATE medications SET status = 'available' WHERE id = %s", [med_id])
        cur.execute("DELETE FROM claims WHERE med_id = %s AND recipient_id = %s", (med_id, recipient_id))
        mysql.connection.commit()
        flash("Claim cancelled successfully. The medication is back in the listings!")
    else:
        flash("⚠️ Error: You cannot cancel a claim that isn't yours.")

    cur.close()
    return redirect(url_for('my_claims'))


@app.route('/my_claims')
def my_claims():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT m.name, m.quantity, c.claim_date, m.status, m.id
        FROM claims c
        JOIN medications m ON c.med_id = m.id
        WHERE c.recipient_id = %s
        ORDER BY c.claim_date DESC
    """, [session['user_id']])
    user_claims = cur.fetchall()
    cur.close()
    return render_template('my_claims.html', claims=user_claims)

@app.route('/generate_qr/<int:med_id>')
def generate_qr(med_id):
    qr_data = f"http://192.168.31.18:5000/verify/{med_id}"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/verify/<int:med_id>')
def verify(med_id):
    if 'user_id' not in session or session.get('role') != 'donor':
        flash("⚠️ Access Denied: Please log in as the Pharmacy to verify this pickup.")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT donor_id FROM medications WHERE id = %s", [med_id])
    med = cur.fetchone()

    if med and med[0] == session['user_id']:
        cur.execute("UPDATE medications SET status = 'delivered' WHERE id = %s", [med_id])
        mysql.connection.commit()
        flash("✅ Transfer Verified successfully!")
    else:
        flash("⚠️ Error: You can only verify medication that you posted.")

    cur.close()
    return redirect(url_for('dashboard'))

@app.route('/leaderboard')
def leaderboard():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT u.full_name, u.impact_points, COALESCE(SUM(m.quantity), 0)
        FROM users u
        LEFT JOIN medications m ON u.id = m.donor_id
        WHERE u.role='donor'
        GROUP BY u.id, u.full_name, u.impact_points
        ORDER BY u.impact_points DESC
    """)
    top_donors = cur.fetchall()

    cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM medications WHERE status = 'delivered'")
    total_saved = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(m.quantity), 0) 
        FROM medications m 
        JOIN claims c ON m.id = c.med_id 
        WHERE DATE(c.claim_date) = CURDATE() AND m.status = 'delivered'
    """)
    today_saved = cur.fetchone()[0]
    cur.close()
    return render_template('leaderboard.html', donors=top_donors, total_saved=int(total_saved), today_saved=int(today_saved))

@app.route('/submit_feedback/<int:med_id>', methods=['POST'])
def submit_feedback(med_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    message = request.form.get('message')
    f_type = request.form.get('type') 
    recipient_id = session['user_id']

    cur = mysql.connection.cursor()
    cur.execute("SELECT donor_id FROM medications WHERE id = %s", [med_id])
    donor_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO feedback (med_id, recipient_id, donor_id, message, type)
        VALUES (%s, %s, %s, %s, %s)
    """, (med_id, recipient_id, donor_id, message, f_type))
    
    mysql.connection.commit()
    cur.close()
    flash("Thank you! Your message has been sent to the pharmacy.")
    return redirect(url_for('my_claims'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
