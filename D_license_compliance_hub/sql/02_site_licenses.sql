-- Facility licenses and permits as of the snapshot.
WITH as_of AS (SELECT value AS d FROM meta WHERE key = 'as_of_date')
SELECT sl.site_license_key, sl.site_key, s.site_name, sl.license_type, sl.fictional_license_key, sl.state_code,
       sl.issue_date, sl.expiry_date, sl.document_flag,
       CAST(julianday(sl.expiry_date) - julianday((SELECT d FROM as_of)) AS INTEGER) AS days_to_expiry
FROM site_licenses sl
JOIN sites s USING (site_key)
ORDER BY sl.site_key, sl.license_type;
