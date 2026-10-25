-- Medical-director relationships (many-to-many, effective-dated) with the director's own license evidence.
WITH as_of AS (SELECT value AS d FROM meta WHERE key = 'as_of_date')
SELECT m.assignment_key, m.site_key, s.site_name, s.opened_date, m.director_staff_key, st.staff_label AS director_label,
       m.relationship_start, m.relationship_end, m.is_primary,
       CASE WHEN m.relationship_start <= (SELECT d FROM as_of)
             AND (m.relationship_end IS NULL OR m.relationship_end >= (SELECT d FROM as_of)) THEN 1 ELSE 0 END AS is_current,
       (SELECT MIN(l.expiry_date) FROM license_registry l WHERE l.staff_key = m.director_staff_key AND l.credential_class = 'MD') AS director_license_expiry,
       (SELECT COUNT(*) FROM document_index d JOIN license_registry l USING (license_record_key)
         WHERE l.staff_key = m.director_staff_key AND l.credential_class = 'MD')                                  AS director_license_docs
FROM medical_director_assignment m
JOIN sites s USING (site_key)
JOIN synthetic_staff st ON st.staff_key = m.director_staff_key
ORDER BY m.site_key, m.relationship_start;
