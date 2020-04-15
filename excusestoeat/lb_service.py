import flask
from flask_cors import CORS
import leaderboard as lb
import json

app = flask.Flask(__name__)
app.config["DEBUG"] = True
CORS(app)

@app.route('/apps/excusestoeat', methods=['GET'])
def home():
    try:
        res = lb.main()
    except:
        res = []
    return json.dumps(res)

app.run(host='0.0.0.0')
