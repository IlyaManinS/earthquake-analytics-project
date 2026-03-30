{% macro earthquake_agg_metrics() %}
    COUNT(*)                    as event_count,
    ROUND(AVG(magnitude), 2)    as avg_magnitude,
    MAX(magnitude)              as max_magnitude,
    MIN(magnitude)              as min_magnitude
{% endmacro %}