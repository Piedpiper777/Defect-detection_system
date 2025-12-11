from flask import Flask, render_template

app = Flask(__name__,
            template_folder='frontend/templates',
            static_folder='frontend/static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/qa')
def qa():
    return render_template('qa.html')  # 你可以创建这个模板

@app.route('/graph')
def graph():
    return render_template('graph_viz.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)