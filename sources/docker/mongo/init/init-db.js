// MongoDB initialization script for Knowlly data processing API

// Switch to the knowlly_data database
db = db.getSiblingDB('knowlly_data');

// Create collections with proper indexes
db.createCollection('system_info');
db.createCollection('processing_logs');

// Create indexes for better performance
db.system_info.createIndex({ "created_at": 1 });
db.processing_logs.createIndex({ "timestamp": 1 });
db.processing_logs.createIndex({ "collection_name": 1 });

// Insert initial system information
db.system_info.insertOne({
    "system_name": "Knowlly Data Processing API",
    "version": "1.0.0",
    "created_at": new Date(),
    "status": "initialized",
    "features": [
        "CSV processing",
        "XLSX processing", 
        "Metadata extraction",
        "MongoDB storage",
        "REST API"
    ]
});

// Create a user for the application (optional - using root user for now)
// db.createUser({
//     user: "knowlly_app",
//     pwd: "knowlly_app_password",
//     roles: [
//         { role: "readWrite", db: "knowlly_data" }
//     ]
// });

print("✅ Knowlly database initialized successfully");
print("📊 Database: knowlly_data");
print("📁 Collections: system_info, processing_logs");
print("🔗 Ready for data processing operations"); 