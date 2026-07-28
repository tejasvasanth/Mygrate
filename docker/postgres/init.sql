-- Seed PostgreSQL test database: users, products, orders, audit_logs
-- 500 rows each, FK relationships, NULLs, implicit enums.

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  phone VARCHAR(30),
  full_name VARCHAR(120),
  status VARCHAR(20) NOT NULL DEFAULT 'active',   -- implicit enum
  is_verified INTEGER NOT NULL DEFAULT 0,         -- implicit boolean 0/1
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE products (
  id SERIAL PRIMARY KEY,
  sku VARCHAR(40) NOT NULL,
  name VARCHAR(200) NOT NULL,
  category VARCHAR(30),                            -- implicit enum
  price NUMERIC(10,2) NOT NULL,
  in_stock BOOLEAN DEFAULT TRUE
);

CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  product_id INTEGER NOT NULL REFERENCES products(id),
  quantity INTEGER NOT NULL DEFAULT 1,
  order_status VARCHAR(20) DEFAULT 'placed',       -- implicit enum
  total NUMERIC(12,2),
  ordered_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_logs (
  id SERIAL PRIMARY KEY,
  actor_id INTEGER REFERENCES users(id),
  action VARCHAR(50) NOT NULL,
  detail TEXT,
  logged_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO users (email, phone, full_name, status, is_verified)
SELECT
  'user' || g || '@example.com',
  CASE WHEN g % 5 = 0 THEN NULL ELSE '+1-555-01' || lpad(g::text, 4, '0') END,
  CASE WHEN g % 11 = 0 THEN NULL ELSE 'Test User ' || g END,
  (ARRAY['active','inactive','banned','pending'])[1 + g % 4],
  g % 2
FROM generate_series(1, 500) g;

INSERT INTO products (sku, name, category, price, in_stock)
SELECT
  'SKU-' || lpad(g::text, 6, '0'),
  'Product ' || g,
  (ARRAY['electronics','books','toys','garden','food'])[1 + g % 5],
  round((random() * 500 + 1)::numeric, 2),
  g % 3 <> 0
FROM generate_series(1, 500) g;

INSERT INTO orders (user_id, product_id, quantity, order_status, total)
SELECT
  1 + g % 500,
  1 + (g * 7) % 500,
  1 + g % 5,
  (ARRAY['placed','shipped','delivered','cancelled'])[1 + g % 4],
  CASE WHEN g % 13 = 0 THEN NULL ELSE round((random() * 900 + 10)::numeric, 2) END
FROM generate_series(1, 500) g;

INSERT INTO audit_logs (actor_id, action, detail)
SELECT
  CASE WHEN g % 7 = 0 THEN NULL ELSE 1 + g % 500 END,
  (ARRAY['login','logout','purchase','update_profile'])[1 + g % 4],
  CASE WHEN g % 3 = 0 THEN NULL ELSE 'detail for event ' || g END
FROM generate_series(1, 500) g;
