from datetime import datetime
import requests
from flask import Flask, request, url_for
from flask_restx import Api, Resource, fields
import sqlite3
from flask import send_file
import numpy as np
import matplotlib.pyplot as plt
import io
import geopandas as gpd
from shapely.geometry import Point
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)
api = Api(app, version='1.0', title='MyCalendar API', description='A time-management and scheduling calendar service')
ns = api.namespace('api/events', description='Events operations')

event = api.model('Event', {
    'id': fields.Integer(readOnly=True, description='The event unique identifier'),
    'name': fields.String(required=True, description='The event name'),
    'date': fields.String(required=True, description='The event date'),
    'from': fields.String(required=True, description='The event start time'),
    'to': fields.String(required=True, description='The event end time'),
    'location': fields.Nested(api.model('Location', {
        'street': fields.String(required=True, description='The event street address'),
        'suburb': fields.String(required=True, description='The event suburb'),
        'state': fields.String(required=True, description='The event state'),
        'post-code': fields.String(required=True, description='The event post code'),
    })),
    'description': fields.String(description='The event description'),
    '_links': fields.Raw(description='The event links'),
    '_metadata': fields.Raw(description='The event metadata'),
    'last-update': fields.String(readOnly=True, description='The event last update timestamp'),  # Add this line
})

event_response = api.model('EventResponse', {
    'id': fields.Integer(readOnly=True, description='The event unique identifier'),
    'last-update': fields.String(readOnly=True, description='The event last update timestamp'),
    '_links': fields.Nested(api.model('Links', {
        'self': fields.Nested(api.model('Self', {
            'href': fields.String(readOnly=True, description='The event self link')
        }))
    }))
})

event_delete_response = api.model('EventDeleteResponse', {
    'message': fields.String(readOnly=True, description='The deletion message'),
    'id': fields.Integer(readOnly=True, description='The event unique identifier'),
})

event_patch = api.model('EventPatch', {
    'name': fields.String(description='The event name'),
    'date': fields.String(description='The event date'),
    'from': fields.String(description='The event start time'),
    'to': fields.String(description='The event end time'),
    'location': fields.Nested(api.model('Location', {
        'street': fields.String(description='The event street address'),
        'suburb': fields.String(description='The event suburb'),
        'state': fields.String(description='The event state'),
        'post-code': fields.String(description='The event post code'),
    })),
    'description': fields.String(description='The event description'),
})

event_list_response = api.model('Event', {
    'id': fields.Integer(description='The unique identifier of the event'),
    'name': fields.String(description='The name of the event'),
    'datetime': fields.String(description='The date and time of the event'),
    'last_update': fields.String(description='The date and time of the last update'),
    '_links': fields.Nested(api.model('Links', {
        'self': fields.String(attribute='href', description='The link to the event details'),
    }), description='The links related to the event')
})


def get_statistics_image(self):
    data = self.get_statistics_json()

    # Generate a bar chart
    x = np.arange(len(data['per-days']))
    plt.bar(x, data['per-days'].values())
    plt.xticks(x, data['per-days'].keys(), rotation='vertical')
    plt.xlabel('Date')
    plt.ylabel('Number of Events')
    plt.title('Number of Events per Day')

    # Save the chart to a buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # Return the image
    return send_file(buf, mimetype='image/png', as_attachment=False)


cities = {
    "Sydney": [-33.865143, 151.209900],
    "Melbourne": [-37.813628, 144.963058],
    "Brisbane": [-27.469770, 153.025131],
    "Perth": [-31.950527, 115.860457],
    "Adelaide": [-34.928499, 138.600746],
    "Canberra": [-35.280937, 149.130009],
    "Hobart": [-42.882138, 147.327195],
}


# 获取天气数据
def get_weather_data(lat, lng):
    url = f"https://www.7timer.info/bin/civil.php?lat={lat}&lng={lng}&ac=1&unit=metric&output=json&product=two"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None


city_weather_data = {}
for city, coords in cities.items():
    weather_data = get_weather_data(coords[0], coords[1])
    city_weather_data[city] = weather_data

# 创建GeoDataFrame
city_points = [Point(xy) for xy in cities.values()]
gdf = gpd.GeoDataFrame(cities.keys(), geometry=city_points, crs="EPSG:4326")

# 转换坐标参考系统以适应底图
gdf = gdf.to_crs(epsg=3857)

print(city_weather_data)


def plot_weather_forecast(date, city_weather_data):
    # 创建一个新的matplotlib图像和坐标轴
    date_object = datetime.strptime(date, '%Y-%m-%d')
    today = datetime.now()
    days_diff = (date_object - today).days
    fig, ax = plt.subplots(figsize=(10, 10))

    # 读取世界地图数据
    world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))

    # 绘制世界地图，限制显示范围为澳大利亚
    world.plot(ax=ax, alpha=0.5, edgecolor="k")
    ax.set_xlim(11000000, 18000000)
    ax.set_ylim(-6000000, 0)

    # 绘制城市和天气预报
    gdf.plot(ax=ax, alpha=0.5, edgecolor="k")
    for idx, row in gdf.iterrows():
        city = row[0]
        point = row['geometry']
        weather_summary = city_weather_data[city]['dataseries'][days_diff]['weather']
        ax.text(point.x, point.y, f"{city}\n{weather_summary}", fontsize=12, ha="center")

    plt.close(fig)
    return fig


def get_statistics_json(self):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()

    # Total number of events
    c.execute("SELECT COUNT(*) FROM events")
    total_count = c.fetchone()[0]

    # Total number of events in current week
    c.execute("SELECT COUNT(*) FROM events WHERE date >= date('now', 'weekday 0', '-7 days') AND date <= date("
              "'now', 'weekday 0')")
    total_current_week = c.fetchone()[0]

    # Total number of events in current month
    c.execute("SELECT COUNT(*) FROM events WHERE date >= date('now', 'start of month') AND date <= date('now', "
              "'start of month', '+1 month', '-1 day')")
    total_current_month = c.fetchone()[0]

    # Number of events per day
    c.execute("SELECT date, COUNT(*) FROM events GROUP BY date")
    per_days = dict(c.fetchall())

    conn.close()

    response_data = {
        "total": total_count,
        "total-current-week": total_current_week,
        "total-current-month": total_current_month,
        "per-days": per_days
    }

    return response_data


def init_db():
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  date TEXT NOT NULL,
                  from_time TEXT NOT NULL,
                  to_time TEXT NOT NULL,
                  street TEXT NOT NULL,
                  suburb TEXT NOT NULL,
                  state TEXT NOT NULL,
                  post_code TEXT NOT NULL,
                  description TEXT,
                  last_update TEXT NOT NULL)''')
    conn.commit()
    conn.close()


init_db()

column_mapping = {
    "from": "from_time",
    "to": "to_time"
}


def delete_event_by_id(event_id):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('DELETE FROM events WHERE id=?', (event_id,))
    deleted_rows = c.rowcount
    conn.commit()
    conn.close()
    return deleted_rows


def get_event_by_id(event_id):
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    c.execute('SELECT * FROM events WHERE id=?', (event_id,))
    result = c.fetchone()
    conn.close()
    return result


def get_metadata(event_date, location):
    event_date = datetime.strptime(event_date, '%d-%m-%Y').strftime('%Y-%m-%d')
    holiday_api_url = "https://date.nager.at/api/v2/publicholidays/2023/AU"
    holiday_response = requests.get(holiday_api_url)
    holiday_data = holiday_response.json()
    holiday = None
    for holiday_item in holiday_data:
        if holiday_item['date'] == event_date:
            holiday = holiday_item['name']
            break

    lat, lon = location['lat'], location['lon']
    weather_api_url = f"http://www.7timer.info/bin/civil.php?lon={lon}&lat={lat}&ac=0&unit=metric&output=json&tzshift=0"
    weather_response = requests.get(weather_api_url)
    weather_data = weather_response.json()
    weather = None
    if 'dataseries' in weather_data:
        for day in weather_data['dataseries']:
            day_date = datetime.fromtimestamp(day['timepoint']).strftime('%Y-%m-%d')
            if day_date == event_date:
                weather = {
                    'temperature': f"{day['temp2m']['max']} C",
                    'humidity': f"{day['rh2m']}%",
                    'wind_speed': f"{day['wind10m_max']} KM",
                    'weather': day['weather']
                }
                break
    event_datetime = datetime.strptime(event_date, "%Y-%m-%d")
    weekend = event_datetime.weekday() >= 5

    metadata = {
        'holiday': holiday,
        'weekend': weekend
    }
    if weather:
        metadata.update(weather)
    return metadata


def is_time_overlap(date1: str, start1: str, end1: str, date2: str, start2: str, end2: str) -> bool:
    datetime_format = '%d-%m-%Y %H:%M'

    datetime_start1 = datetime.strptime(f'{date1} {start1}', datetime_format)
    datetime_end1 = datetime.strptime(f'{date1} {end1}', datetime_format)
    datetime_start2 = datetime.strptime(f'{date2} {start2}', datetime_format)
    datetime_end2 = datetime.strptime(f'{date2} {end2}', datetime_format)

    return datetime_start1 < datetime_end2 and datetime_start2 < datetime_end1


@ns.route('/')
class EventList(Resource):
    @api.param('page', 'The page number', type=int)
    @api.param('page_size', 'The number of events per page', type=int)
    @api.param('order', '排序条件，用逗号分隔的字符串，例如：+name,-datetime', type=str)
    @api.param('filter', '过滤条件，用逗号分隔的字符串，例如：id,name,datetime', type=str)
    @ns.marshal_with(event_list_response)
    def get(self):
        page = request.args.get('page', default=1, type=int)
        page_size = request.args.get('page_size', default=10, type=int)
        order = request.args.get('order', default="+id", type=str)
        filter = request.args.get('filter', default="id,name", type=str)

        # 处理排序参数
        order_columns = order.split(',')
        order_by = []
        for col in order_columns:
            if col.startswith('+'):
                order_by.append((col[1:], "ASC"))
            elif col.startswith('-'):
                order_by.append((col[1:], "DESC"))

        # 处理过滤参数
        filter_columns = filter.split(',')

        # 根据排序和过滤条件查询活动列表
        conn = sqlite3.connect('events.db')
        c = conn.cursor()

        # 获取活动总数
        c.execute("SELECT COUNT(*) FROM events")
        total_count = c.fetchone()[0]

        # 构建查询语句
        select_columns = [col if col != "datetime" else "date || ' ' || from_time AS datetime" for col in
                          filter_columns]
        query = "SELECT " + ", ".join(select_columns) + " FROM events"

        order_columns = [("date || ' ' || from_time" if col == "datetime" else col, direction) for col, direction in
                         order_by]
        if order_columns:
            query += " ORDER BY " + ", ".join([f"{col} {direction}" for col, direction in order_columns])

        c.execute(query)
        result = c.fetchall()

        # 分页
        start = (page - 1) * page_size
        end = page * page_size
        result = result[start:end]

        conn.close()

        # 将查询结果转换为字典
        print("Result:", result)  # 打印查询结果
        result_dicts = []
        for row in result:
            event_dict = {}
            for field, value in zip(filter_columns, row):
                if field == 'date' or field == 'from_time':
                    if 'datetime' not in event_dict:
                        event_dict['datetime'] = value
                    else:
                        event_dict['datetime'] += " " + value
                else:
                    event_dict[field] = value

            event_dict["_links"] = {
                "self": {"href": url_for('api/events_event', event_id=event_dict['id'], _external=True)}}
            print("Event Dict:", event_dict)  # 打印构建的事件字典
            result_dicts.append(event_dict)

        # 构建_links
        self_link = f"/api/events?order={order}&page={page}&size={page_size}&filter={filter}"
        prev_link = f"/api/events?order={order}&page={page - 1}&size={page_size}&filter={filter}" if page > 1 else None
        next_link = f"/api/events?order={order}&page={page + 1}&size={page_size}&filter={filter}" if (page * page_size) < total_count else None

        links = {
            "self": {"href": self_link},
            "prev": {"href": prev_link} if prev_link else None,
            "next": {"href": next_link} if next_link else None,
        }

        metadata = {"total_events": total_count, "_links": links, "page": page, "page_size": page_size}

        # Create response object
        response_data = {
            "events": result_dicts,
            "metadata": metadata,
        }

        return response_data

    @ns.expect(event)
    @ns.marshal_with(event_response, code=201)
    def post(self):
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        new_event = request.json
        last_update = datetime.utcnow().isoformat()
        c.execute('SELECT * FROM events')
        existing_events = c.fetchall()
        for existing_event in existing_events:
            existing_event_dict = {
                "id": existing_event[0],
                "date": existing_event[2],
                "from": existing_event[3],
                "to": existing_event[4]
            }
            if is_time_overlap(new_event["date"], new_event["from"], new_event["to"], existing_event_dict["date"],
                               existing_event_dict["from"], existing_event_dict["to"]):
                raise ValueError("The new event overlaps with an existing event.")
        c.execute('''INSERT INTO events (name, date, from_time, to_time, street, suburb, state, post_code, 
        description, last_update) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            new_event['name'], new_event['date'], new_event['from'], new_event['to'], new_event['location']['street'],
            new_event['location']['suburb'], new_event['location']['state'], new_event['location']['post-code'],
            new_event['description'], last_update))
        event_id = c.lastrowid
        conn.commit()
        conn.close()
        return {
                   'id': event_id,
                   'last-update': last_update,
                   '_links': {
                       'self': {
                           'href': f'/events/{event_id}'
                       }
                   }
               }, 201


@ns.route('/<int:event_id>')
@api.response(404, 'Event not found')
@ns.param('event_id', 'The event identifier')
class Event(Resource):
    @ns.marshal_with(event)
    def get(self, event_id):
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('SELECT * FROM events WHERE id=?', (event_id,))
        result = c.fetchone()
        conn.close()

        if result is not None:
            metadata = get_metadata(result[2], {'lat': -33.865143, 'lon': 151.209900})
            return {
                'id': result[0],
                'name': result[1],
                'date': datetime.strptime(result[2], '%d-%m-%Y').strftime('%d-%m-%Y'),
                'from': result[3],
                'to': result[4],
                'location': {'street': result[5], 'suburb': result[6], 'state': result[7], 'post-code': result[8]},
                'description': result[9],
                '_links': {'self': {'href': f'http://localhost:5000/api/events/{result[0]}'}},
                '_metadata': metadata,
                'last-update': result[10]
            }
        else:
            api.abort(404, 'Event not found')

    @ns.expect(event_patch)
    @ns.marshal_with(event_response)
    def patch(self, event_id):
        conn = sqlite3.connect('events.db')
        c = conn.cursor()
        c.execute('SELECT * FROM events WHERE id=?', (event_id,))
        result = c.fetchone()
        if result is None:
            api.abort(404, 'Event not found')

        patched_event = request.json
        last_update = datetime.utcnow().isoformat()
        c.execute('SELECT * FROM events')
        existing_events = c.fetchall()
        for existing_event in existing_events:
            existing_event_dict = {
                "id": existing_event[0],
                "date": existing_event[2],
                "from": existing_event[3],
                "to": existing_event[4]
            }
            if existing_event_dict["id"] == event_id:
                continue
            if is_time_overlap(patched_event.get("date", result[2]), patched_event.get("from", result[3]),
                               patched_event.get("to", result[4]),
                               existing_event_dict["date"], existing_event_dict["from"], existing_event_dict["to"]):
                raise ValueError("The modified event overlaps with an existing event.")
        for key, value in patched_event.items():
            db_column = column_mapping.get(key, key)
            if key == 'location':
                for loc_key, loc_value in value.items():
                    c.execute(f'UPDATE events SET {loc_key}=? WHERE id=?', (loc_value, event_id))
            else:
                c.execute(f'UPDATE events SET "{db_column}"=? WHERE id=?', (value, event_id))

        c.execute('UPDATE events SET last_update=? WHERE id=?', (last_update, event_id))
        conn.commit()
        conn.close()
        return {
                   'id': event_id,
                   'last-update': last_update,
                   '_links': {
                       'self': {
                           'href': f'/events/{event_id}'
                       }
                   }
               }, 200

    @ns.marshal_with(event_delete_response, code=200)
    def delete(self, event_id):
        deleted_rows = delete_event_by_id(event_id)
        if deleted_rows == 0:
            api.abort(404, f"Event {event_id} doesn't exist")

        response = {
            'message': f"The event with id {event_id} was removed from the database!",
            'id': event_id
        }
        return response, 200


@ns.route('/statistics')
class EventStatistics(Resource):
    @api.param('format', 'The response format (json or image)', type=str)
    def get(self):
        format = request.args.get('format', default='json', type=str)
        if format not in ('json', 'image'):
            return {"error": "Invalid format"}, 400

        if format == 'json':
            return self.get_statistics_json()
        elif format == 'image':
            return self.get_statistics_image()


@app.route('/weather', methods=['GET'])
def get_weather():
    date = request.args.get('date', default=datetime.now().strftime('%Y-%m-%d'), type=str)
    fig = plot_weather_forecast(date, city_weather_data)

    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png', dpi=300, bbox_inches="tight")
    plt.close(fig)
    img_buffer.seek(0)

    # Send the buffer as an image response
    return send_file(img_buffer, mimetype='image/png')


if __name__ == '__main__':
    app.run(debug=True)
