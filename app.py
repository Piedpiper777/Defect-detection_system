from flask import Flask, render_template

app = Flask(__name__,
            template_folder='frontend/templates',
            static_folder='frontend/static')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/llmkg')
def llmkg():
    return render_template('llmkg.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)