-- T-103 License records with no supporting document, excluding duplicate entries of the same license (SYNTHETIC).
SELECT l.license_record_key, s.staff_label, l.credential_class, l.state_code, l.expiry_date,
       l.document_flag AS register_says_on_file,
       CASE WHEN l.document_flag = 0 THEN 'Register shows no document'
            ELSE 'Register says on file, but the document library has nothing' END AS gap
FROM license_registry l
JOIN synthetic_staff s ON s.staff_key = l.staff_key
WHERE (l.document_flag = 0
       OR NOT EXISTS (SELECT 1 FROM document_index d WHERE d.license_record_key = l.license_record_key))
  AND NOT EXISTS (SELECT 1 FROM license_registry e WHERE e.fictional_license_key = l.fictional_license_key
                  AND e.license_record_key < l.license_record_key)
ORDER BY l.expiry_date;
