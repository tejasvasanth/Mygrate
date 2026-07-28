// Seed MongoDB test database: users collection with embedded orders array.
// Mixed schema — some docs carry extra fields.

db = db.getSiblingDB('testdb');

const statuses = ['active', 'inactive', 'banned', 'pending'];
const categories = ['electronics', 'books', 'toys', 'garden', 'food'];

const users = [];
for (let i = 1; i <= 500; i++) {
  const doc = {
    email: `mongo_user${i}@example.com`,
    full_name: i % 11 === 0 ? null : `Mongo User ${i}`,
    status: statuses[i % 4],
    is_verified: i % 2 === 0,
    orders: [],
  };
  const orderCount = i % 6; // 0–5 embedded orders
  for (let j = 0; j < orderCount; j++) {
    doc.orders.push({
      sku: `OSKU-${i}-${j}`,
      category: categories[(i + j) % 5],
      quantity: 1 + (j % 4),
      total: Math.round(Math.random() * 90000) / 100,
      placed_at: new Date(Date.now() - i * 86400000),
    });
  }
  // Mixed schema: ~20% of docs have extra fields
  if (i % 5 === 0) {
    doc.loyalty_tier = ['bronze', 'silver', 'gold'][i % 3];
    doc.phone = `+91-98${String(i).padStart(8, '0')}`;
  }
  users.push(doc);
}
db.users.insertMany(users);
db.users.createIndex({ email: 1 }, { unique: true });
