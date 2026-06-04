from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import os
import secrets
from functools import wraps
import utils as utils_mod
from utils import (answer_query, health_check, validate_employee_credentials, get_employee_display_name)
from graph import run_hr_bot
from employee_db import get_employee

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(hours=8)

# Simple in-memory storage for chat history
chat_history = {}


def clean_response_citations(response: str) -> str:
    """Remove all possible citation patterns from response."""
    citation_patterns = [
        "(Source:",
        "(source:",
        "Source:",
        "source:",
        "(Policy_",
        "(policy_",
        "Policy_",
        "policy_",
        "(General HR Knowledge",
        "(Employee Database)",
        "Employee Database",
        "- Please verify with HR for specific policies)",
        "Please verify with HR for specific policies",
        "(Source: General HR Knowledge",
        "(Source: Policy_",
        "(Source: Employee Database)"
    ]

    for pattern in citation_patterns:
        if pattern in response:
            response = response.split(pattern)[0].strip()

    # Clean up trailing punctuation
    response = response.rstrip(" -.,;:")

    return response


def login_required(f):
    """Decorator to require login for protected routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'emp_id' not in session:
            flash('Please log in to access the HR Bot.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """Home page - redirect to chat if logged in, otherwise to login."""
    if 'emp_id' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Employee login page with ID, Name and Password verification."""

    if request.method == 'POST':

        emp_id = request.form.get('emp_id', '').strip()
        emp_name = request.form.get('emp_name', '').strip()
        password = request.form.get('password', '').strip()

        if not emp_id:
            flash('Please enter your Employee ID.', 'error')
            return render_template('login.html')

        if not emp_name:
            flash('Please enter your Employee Name.', 'error')
            return render_template('login.html')

        if not password:
            flash('Please enter your Password.', 'error')
            return render_template('login.html')

        if len(emp_id) < 3:
            flash('Employee ID must be at least 3 characters long.', 'error')
            return render_template('login.html')

        if len(emp_name) < 2:
            flash('Please enter a valid employee name.', 'error')
            return render_template('login.html')

        is_valid, employee_data, error_message = (
            validate_employee_credentials(
                emp_id,
                emp_name,
                password
            )
        )

        if is_valid:

            session['emp_id'] = emp_id
            session['emp_name'] = get_employee_display_name(employee_data)
            session.permanent = True

            if emp_id not in chat_history:
                chat_history[emp_id] = []

            print(f"Successful login: {emp_id} - {session['emp_name']}")

            flash(
                f'Welcome back, {session["emp_name"]}!',
                'success'
            )

            return redirect(url_for('chat'))

        flash(error_message, 'error')

        print(
            f"Failed login attempt: "
            f"ID={emp_id}, "
            f"Name={emp_name}"
        )

        return render_template('login.html')

    return render_template('login.html')


@app.route('/api/check_employee/<emp_id>')
@login_required
def check_employee_details(emp_id):
    """Debug route to check employee details - remove in production"""
    if not session.get('is_hr'):
        return jsonify({'error': 'Access denied'}), 403

    employee_data = get_employee(emp_id)

    if employee_data:
        safe_data = {
            'emp_id': employee_data.get('Employee_Id'),
            'name': employee_data.get('Name'),
            'department': employee_data.get('Department'),
            'position': employee_data.get('Position'),
            'status': employee_data.get('Emp_Status')
        }
        return jsonify(safe_data)
    else:
        return jsonify({'error': 'Employee not found'}), 404


@app.route('/logout')
def logout():
    """Logout and clear session."""
    emp_name = session.get('emp_name', 'User')
    session.clear()
    flash(f'Goodbye, {emp_name}! You have been logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/chat')
@login_required
def chat():
    """Main chat interface."""
    emp_id = session['emp_id']
    emp_name = session['emp_name']

    # Get recent chat history for this user
    recent_chats = chat_history.get(emp_id, [])[-20:]

    return render_template('chat.html', 
                           emp_name=emp_name, 
                           emp_id=emp_id,
                           chat_history=recent_chats)


@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """API endpoint to handle chat messages."""
    try:
        data = request.get_json()
        query = data.get('message', '').strip()

        if not query:
            return jsonify({'error': 'Please enter a message.'}), 400

        emp_id = session['emp_id']
        emp_name = session['emp_name']

        # DEBUG: print working directory and collection size
        try:
            print("WORKING DIR:", os.getcwd())
            # utils_mod._collection is the Chroma collection object
            coll_count = getattr(utils_mod, '_collection', None)
            if coll_count is not None:
                try:
                    count = utils_mod._collection.count()
                except Exception:
                    # fallback to .get() length
                    try:
                        count = len(utils_mod._collection.get().get('ids', []))
                    except Exception:
                        count = 'unknown'
            else:
                count = 'no_collection'
            print("CHROMA COLLECTION COUNT:", count)
        except Exception as e:
            print("Debug error while checking collection:", e)

        # DEBUG: retrieve context directly and log a snippet
        try:
            ctx = utils_mod.retrieve_context(query)
            print("RETRIEVED CONTEXT (first 400 chars):", (ctx or "<EMPTY>")[:400])
        except Exception as e:
            print("Error retrieving context:", e)
            ctx = ""

        # Get response from the HR bot
        try:
            # Use the graph-based runner if available, otherwise use direct answer_query
            if 'run_hr_bot' in globals():
                response = run_hr_bot(query, emp_id)
            else:
                response = answer_query(query, emp_id)
        except Exception as e:
            print("Error during bot processing:", e)
            response = "I'm sorry, I encountered an error while processing your request. Please contact HR directly."

        # Clean any remaining citations from response (multiple layers of cleaning)
        response = clean_response_citations(response)

        # Store chat history
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chat_entry = {
            'timestamp': timestamp,
            'user_message': query,
            'bot_response': response
        }

        if emp_id not in chat_history:
            chat_history[emp_id] = []

        chat_history[emp_id].append(chat_entry)

        # Keep only last 50 messages per user to manage memory
        if len(chat_history[emp_id]) > 50:
            chat_history[emp_id] = chat_history[emp_id][-50:]

        return jsonify({
            'response': response,
            'timestamp': timestamp
        })

    except Exception as e:
        print("API_CHAT ERROR:", e)
        return jsonify({'error': 'Server error occurred. Please contact HR for assistance.'}), 500


@app.route('/profile')
@login_required
def profile():
    """Employee profile page."""
    emp_id = session['emp_id']
    employee_data = get_employee(emp_id)

    if not employee_data:
        flash('Could not load your profile. Please contact HR.', 'error')
        return redirect(url_for('chat'))

    return render_template('profile.html', employee=employee_data)


@app.route('/api/clear_chat', methods=['POST'])
@login_required
def clear_chat():
    """Clear chat history for current user."""
    emp_id = session['emp_id']
    if emp_id in chat_history:
        chat_history[emp_id] = []
    return jsonify({'success': True})


@app.route('/debug')
def debug():
    """Simple debug endpoint to inspect vector DB and a sample retrieval."""
    try:
        coll = getattr(utils_mod, '_collection', None)
        if coll is None:
            return jsonify({'error': 'collection_not_loaded'}), 500

        # Try to get count in a robust way
        try:
            count = coll.count()
        except Exception:
            count = len(coll.get().get('ids', []))

        # Get a small sample of documents and metadata
        try:
            data = coll.get()
            sample_docs = [{
                'id': data['ids'][i],
                'policy': data['metadatas'][i].get('policy', ''),
                'content_snippet': data['documents'][i][:300]
            } for i in range(min(5, len(data.get('ids', []))))]
        except Exception:
            sample_docs = []

        # Also test a retrieval
        test_q = request.args.get('q', 'leave policy')
        try:
            retrieved = utils_mod.retrieve_context(test_q)
        except Exception as e:
            retrieved = f"error: {e}"

        return jsonify({
            'cwd': os.getcwd(),
            'collection_count': count,
            'sample_docs': sample_docs,
            'retrieved_for_test_q': (retrieved[:1000] if isinstance(retrieved, str) else str(retrieved))
        })

    except Exception as e:
        print("DEBUG ROUTE ERROR:", e)
        return jsonify({'error': 'debug_failed', 'detail': str(e)}), 500


@app.route('/health')
def health():
    """Health check endpoint for monitoring."""
    status = health_check()
    status_code = 200 if all([status['gemini_api'], status['vector_db'], status['employee_db']]) else 500
    return jsonify(status), status_code


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error='Page not found', error_code=404), 404


@app.errorhandler(500)
def server_error(error):
    return render_template('error.html', error='Internal server error', error_code=500), 500


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

    print("Starting HR Bot Flask server...")
    print("Visit: http://127.0.0.1:5000")

    # Print working directory and collection size at startup
    try:
        print("STARTUP WORKING DIR:", os.getcwd())
        coll = getattr(utils_mod, '_collection', None)
        if coll is not None:
            try:
                print("STARTUP CHROMA COUNT:", coll.count())
            except Exception:
                try:
                    print("STARTUP CHROMA COUNT (fallback):", len(coll.get().get('ids', [])))
                except Exception:
                    print("STARTUP CHROMA COUNT: unknown")
        else:
            print("STARTUP CHROMA: collection not loaded")
    except Exception as e:
        print("Startup debug error:", e)

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000)
