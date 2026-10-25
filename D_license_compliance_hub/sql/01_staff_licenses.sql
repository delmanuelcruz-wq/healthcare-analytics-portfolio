-- Staff license register as of the snapshot, with document evidence and duplicate detection.
-- SYNTHETIC DEMONSTRATION - fictional staff labels and MOCK- license IDs only.
WITH as_of AS (SELECT value AS d FROM meta WHERE key = 'as_of_date')
SELECT l.license_record_key, l.staff_key, s.staff_label, s.role, s.home_site_key, si.site_name AS home_site_name,
       l.fictional_license_key, l.credential_class, l.license_scope, l.state_code,
       l.issue_date, l.expiry_date, l.verified_date, l.recorded_status, l.document_flag,
       CAST(julianday(l.expiry_date) - julianday((SELECT d FROM as_of)) AS INTEGER)                   AS days_to_expiry,
       (SELECT COUNT(*) FROM document_index d WHERE d.license_record_key = l.license_record_key)       AS documents_on_file,
       (SELECT MIN(e.license_record_key) FROM license_registry e
         WHERE e.fictional_license_key = l.fictional_license_key)                                      AS first_record_key
FROM license_registry l
JOIN synthetic_staff s USING (staff_key)
JOIN sites si ON si.site_key = s.home_site_key
ORDER BY l.expiry_date, l.license_record_key;
