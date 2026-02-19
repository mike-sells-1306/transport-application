-- Database schema for account management system using MySQL
-- Entities: User, Route, Saves (many-to-many relationship), Notification, UserWeather

CREATE TABLE User (
    userID INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    userName VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    colorblindmode BOOLEAN DEFAULT FALSE
);

CREATE TABLE Route (
    routeID INT AUTO_INCREMENT PRIMARY KEY,
    routeName VARCHAR(100) NOT NULL,
    routeStart VARCHAR(100) NOT NULL,
    routeEnd VARCHAR(100) NOT NULL,
    startTime DATETIME NULL,
    endTime DATETIME NULL,
    disruption TEXT NULL,
    CONSTRAINT uq_route_signature UNIQUE (routeName, routeStart, routeEnd, startTime, endTime)
);

CREATE TABLE Saves (
    userID INT NOT NULL,
    routeID INT NOT NULL,
    PRIMARY KEY (userID, routeID),
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE,
    FOREIGN KEY (routeID) REFERENCES Route(routeID) ON DELETE CASCADE
);

CREATE TABLE Notification (
    notificationID INT AUTO_INCREMENT PRIMARY KEY,
    userID INT NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE
);

CREATE TABLE UserWeather (
    userID INT NOT NULL,
    location VARCHAR(100) NOT NULL,
    PRIMARY KEY (userID, location),
    FOREIGN KEY (userID) REFERENCES User(userID) ON DELETE CASCADE
);
