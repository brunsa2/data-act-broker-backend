SELECT
    row_number,
    gross_outlays_undelivered_fyb,
    ussgl480200_undelivered_or_fyb
FROM object_class_program_activity
WHERE submission_id = {} AND
    COALESCE(gross_outlays_undelivered_fyb, 0) <> COALESCE(ussgl480200_undelivered_or_fyb, 0)