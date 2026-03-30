{% macro filter_earthquakes() %}
    event_type = 'earthquake'
    AND magnitude IS NOT NULL
{% endmacro %}