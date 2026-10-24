CREATE DATABASE IF NOT EXISTS student_performance_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE student_performance_db;

CREATE TABLE IF NOT EXISTS students (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    student_id    VARCHAR(50)  NOT NULL,
    student_name  VARCHAR(150) NOT NULL,
    branch        VARCHAR(100) NOT NULL,
    semester      INT          NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_student_id (student_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS subjects (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    subject_name  VARCHAR(150) NOT NULL,
    UNIQUE KEY uq_subject_name (subject_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS student_marks (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    student_id    INT NOT NULL,
    subject_id    INT NOT NULL,
    marks         DECIMAL(5,2) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE KEY uq_student_subject (student_id, subject_id),
    CONSTRAINT chk_marks_range CHECK (marks >= 0 AND marks <= 100)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS student_performance (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    student_id            INT NOT NULL,
    overall_percentage    DECIMAL(5,2) NOT NULL,
    performance_category  VARCHAR(20) NOT NULL,
    risk_level            VARCHAR(20),
    risk_reasoning        VARCHAR(500),
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE KEY uq_perf_student (student_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS uploads (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    filename        VARCHAR(255) NOT NULL,
    num_students    INT NOT NULL,
    num_subjects    INT NOT NULL,
    uploaded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
