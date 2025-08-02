// MongoDB initialization script for Knowlly data processing API

// First, switch to admin database to create the root user
db = db.getSiblingDB('admin');

// Create the admin user if it doesn't exist
try {
    db.createUser({
        user: "admin",
        pwd: "knowlly123",
        roles: [
            { role: "userAdminAnyDatabase", db: "admin" },
            { role: "readWriteAnyDatabase", db: "admin" },
            { role: "dbAdminAnyDatabase", db: "admin" },
            { role: "clusterAdmin", db: "admin" }
        ]
    });
    print("✅ Admin user created successfully");
} catch (error) {
    if (error.code === 51003) {
        print("ℹ️  Admin user already exists");
    } else {
        print("❌ Error creating admin user: " + error.message);
    }
}

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

// Create a specific user for the application
try {
    db.createUser({
        user: "knowlly_app",
        pwd: "knowlly_app_password",
        roles: [
            { role: "readWrite", db: "knowlly_data" }
        ]
    });
    print("✅ Application user created successfully");
} catch (error) {
    if (error.code === 51003) {
        print("ℹ️  Application user already exists");
    } else {
        print("❌ Error creating application user: " + error.message);
    }
}

print("✅ Knowlly database initialized successfully");
print("📊 Database: knowlly_data");
print("📁 Collections: system_info, processing_logs");
print("👤 Users: admin (root), knowlly_app (application)");
print("🔗 Ready for data processing operations"); 