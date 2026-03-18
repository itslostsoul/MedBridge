import MySQLdb

# --- PUT YOUR AIVEN DETAILS HERE ---
AIVEN_HOST = "mysql-15e12385-nimalyd20-bfe1.j.aivencloud.com"
AIVEN_PORT = 16657  # Change to your port number
AIVEN_USER = "avnadmin"
AIVEN_PASSWORD = "AVNS_akVQBE4Ujva0j3Kbjw4"
AIVEN_DB = "defaultdb"
# -----------------------------------

print("⏳ Connecting to Aiven Cloud...")

try:
    db = MySQLdb.connect(
        host=AIVEN_HOST,
        port=AIVEN_PORT,
        user=AIVEN_USER,
        password=AIVEN_PASSWORD,
        database=AIVEN_DB,
        connect_timeout=10
    )
    cur = db.cursor()
    print("✅ Connected! Building tables...")

    # The perfect MedBridge Schema
    tables_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        full_name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        role ENUM('donor', 'recipient') NOT NULL,
        impact_points INT DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS medications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        donor_id INT NOT NULL,
        name VARCHAR(255) NOT NULL,
        quantity INT NOT NULL,
        status ENUM('available', 'claimed', 'delivered') DEFAULT 'available',
        expiry_time DATETIME NOT NULL,
        FOREIGN KEY (donor_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS claims (
        id INT AUTO_INCREMENT PRIMARY KEY,
        med_id INT NOT NULL,
        recipient_id INT NOT NULL,
        claim_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (med_id) REFERENCES medications(id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS feedback (
        id INT AUTO_INCREMENT PRIMARY KEY,
        med_id INT NOT NULL,
        recipient_id INT NOT NULL,
        donor_id INT NOT NULL,
        message TEXT NOT NULL,
        type ENUM('feedback', 'complaint') NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (med_id) REFERENCES medications(id) ON DELETE CASCADE,
        FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (donor_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """
    
    # Execute the table creation
    for statement in tables_sql.split(';'):
        if statement.strip():
            cur.execute(statement)
            
    db.commit()
    cur.close()
    db.close()
    print("🚀 SUCCESS! Your cloud database is fully built and ready.")

except Exception as e:
    print(f"❌ ERROR: {e}")