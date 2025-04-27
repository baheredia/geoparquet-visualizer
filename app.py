from flask import Flask, render_template, request, jsonify
import duckdb
import json


app = Flask(__name__)

# Utility function to create a new DuckDB connection with spatial extension loaded
def create_duckdb_connection():
    con = duckdb.connect()
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")
    return con

@app.route('/')
def index():
    return render_template('index.html')

current_file = 'files/test-bucket/network.parquet/*.parquet'

@app.route('/features')
def features():
    # Modify this to point to your GeoParquet file
    global current_file

    bbox = request.args.get('bbox')  # Expected format: minX,minY,maxX,maxY
    new_file = request.args.get('file')
    if new_file:
        current_file = new_file
        if new_file.endswith('.parquet'):
            current_file = f'{new_file}/*.parquet'

    with create_duckdb_connection() as con:
        if bbox:
            minx, miny, maxx, maxy = map(float, bbox.split(','))
            buffer_x = (maxx - minx) * 0.4  # 10% buffer
            buffer_y = (maxy - miny) * 0.4
            minx -= buffer_x
            miny -= buffer_y
            maxx += buffer_x
            maxy += buffer_y
            query = f"""
                SELECT *, ST_AsGeoJSON(geometry) AS geojson
                FROM parquet_scan('{current_file}')
                WHERE ST_Intersects(geometry, ST_MakeEnvelope({minx}, {miny}, {maxx}, {maxy}))
                LIMIT 1000
            """
        else:
            query = f"""
                SELECT *, ST_AsGeoJSON(geometry) AS geojson
                FROM parquet_scan('{current_file}')
                LIMIT 1000
            """
        results = con.execute(query).fetchall()
        columns = [desc[0] for desc in con.description]
    geo_idx = columns.index('geojson')
    print(f"results: {len(results)}")
    features = []
    for idx, row in enumerate(results):
        properties = {col: row[i] for i, col in enumerate(columns) if i != geo_idx and col != 'geometry'}
        features.append({
            "type": "Feature",
            "id": idx,  # <<< Add this line
            "geometry": json.loads(row[geo_idx]),
            "properties": properties
        })
    return jsonify({"type": "FeatureCollection", "features": features})

@app.route('/flagged_features')
def flagged_features():
    global current_file
    query = f"""
        SELECT *, ST_AsGeoJSON(geometry) AS geojson
        FROM parquet_scan('{current_file}')
        WHERE flagged = true
        ORDER BY osmWayId, edgeKeyId
    """
    with create_duckdb_connection() as con:
        results = con.execute(query).fetchall()
        columns = [desc[0] for desc in con.description]
    geo_idx = columns.index('geojson')
    features = []
    for idx, row in enumerate(results):
        properties = {col: row[i] for i, col in enumerate(columns) if i != geo_idx and col != 'geometry'}
        features.append({
            "type": "Feature",
            "id": idx,
            "geometry": json.loads(row[geo_idx]),
            "properties": properties
        })
    return jsonify({"type": "FeatureCollection", "features": features})

if __name__ == '__main__':
    app.run(debug=True)