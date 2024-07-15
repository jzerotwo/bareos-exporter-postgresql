# Adding Prometheus User to PostgreSQL and Executing bareos-exporter-postgresql.py

To integrate Bareos Exporter with Prometheus and PostgreSQL, follow these steps:

1. **Adding Prometheus User to PostgreSQL:**

    - Log in to your PostgreSQL database as a superuser.
    - Create a new user for Prometheus by running the following command:
      ```
      CREATE USER prometheus WITH PASSWORD 'your_password';
      ```
    - Grant necessary privileges to the Prometheus user:
      ```
      GRANT SELECT ON TABLE pool TO prometheus;
      GRANT SELECT ON TABLE media TO prometheus;
      GRANT SELECT ON TABLE log TO prometheus
      ```
    - exit the PostgreSQL database.
      ```
      \q
      ```

2. **Executing bareos-exporter-postgresql.py:**

    - Clone the Bareos Exporter repository to your desired location:
      ```
      git clone https://github.com/bareos/bareos-exporter.git
      ```
    - Navigate to the `bareos-exporter` directory:
      ```
      cd bareos-exporter
      ```
    - Install the required dependencies:
      ```
      pip install -r requirements.txt
      ```
    - Edit the `bareos-exporter-postgresql.py` file and update the PostgreSQL connection details, including the host, port, database name, username, and password.
    - Save the changes and exit the file.
    - Run the `bareos-exporter-postgresql.py` script:
      ```
      python bareos-exporter-postgresql.py
      ```
    - The Bareos Exporter should now be running and exposing metrics for Prometheus to scrape.

For more detailed information, please refer to the Bareos Exporter documentation.
