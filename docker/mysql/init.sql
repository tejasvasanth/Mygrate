-- Seed MySQL test database: same schema as PostgreSQL seed, MySQL syntax.

CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(30),
  full_name VARCHAR(120),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  is_verified TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sku VARCHAR(40) NOT NULL,
  name VARCHAR(200) NOT NULL,
  category VARCHAR(30),
  price DECIMAL(10,2) NOT NULL,
  in_stock TINYINT(1) DEFAULT 1
);

CREATE TABLE orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  order_status VARCHAR(20) DEFAULT 'placed',
  total DECIMAL(12,2),
  ordered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  actor_id INT,
  action VARCHAR(50) NOT NULL,
  detail TEXT,
  logged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (actor_id) REFERENCES users(id)
);

-- Recursive CTE seeding (MySQL 8+)
INSERT INTO users (email, phone, full_name, status, is_verified)
WITH RECURSIVE seq(g) AS (
  SELECT 1 UNION ALL SELECT g + 1 FROM seq WHERE g < 500
)
SELECT
  CONCAT('mysql_user', g, '@example.com'),
  IF(g % 5 = 0, NULL, CONCAT('+44-777-', LPAD(g, 6, '0'))),
  IF(g % 11 = 0, NULL, CONCAT('MySQL User ', g)),
  ELT(1 + g % 4, 'active', 'inactive', 'banned', 'pending'),
  g % 2
FROM seq;

INSERT INTO products (sku, name, category, price, in_stock)
WITH RECURSIVE seq(g) AS (
  SELECT 1 UNION ALL SELECT g + 1 FROM seq WHERE g < 500
)
SELECT
  CONCAT('MSKU-', LPAD(g, 6, '0')),
  CONCAT('MySQL Product ', g),
  ELT(1 + g % 5, 'electronics', 'books', 'toys', 'garden', 'food'),
  ROUND(RAND() * 500 + 1, 2),
  g % 3 <> 0
FROM seq;

INSERT INTO orders (user_id, product_id, quantity, order_status, total)
WITH RECURSIVE seq(g) AS (
  SELECT 1 UNION ALL SELECT g + 1 FROM seq WHERE g < 500
)
SELECT
  1 + g % 500,
  1 + (g * 7) % 500,
  1 + g % 5,
  ELT(1 + g % 4, 'placed', 'shipped', 'delivered', 'cancelled'),
  IF(g % 13 = 0, NULL, ROUND(RAND() * 900 + 10, 2))
FROM seq;

INSERT INTO audit_logs (actor_id, action, detail)
WITH RECURSIVE seq(g) AS (
  SELECT 1 UNION ALL SELECT g + 1 FROM seq WHERE g < 500
)
SELECT
  IF(g % 7 = 0, NULL, 1 + g % 500),
  ELT(1 + g % 4, 'login', 'logout', 'purchase', 'update_profile'),
  IF(g % 3 = 0, NULL, CONCAT('detail for event ', g))
FROM seq;
