# Database schema for account management system using MySQL
# Entities: User, Route, Saves (many-to-many relationship)

# User Table
CREATE TABLE User (
    userID INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    userName VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    colorblindmode BOOLEAN DEFAULT FALSE
);

# Route Table
CREATE TABLE Route (
    routeID INT AUTO_INCREMENT PRIMARY KEY,
    routeName VARCHAR(100) NOT NULL,
    routeStart VARCHAR(100) NOT NULL,
    routeEnd VARCHAR(100) NOT NULL,
    startTime DATETIME NOT NULL,
    endTime DATETIME NOT NULL,
    disruption TEXT
);

# Saves Table (Many-to-Many relationship between User and Route)
CREATE TABLE Saves (
    userID INT,
    routeID INT,
    PRIMARY KEY (userID, routeID),
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (routeID) REFERENCES Route(routeID) ON DELETE CASCADE
);
