# app.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import mysql.connector
from sqlalchemy import create_engine
import pandas as pd
from sqlalchemy.sql import text  # Import the text function

# Database configuration
config = st.secrets["mysql"]

# Create SQLAlchemy engine
def get_engine():
    return create_engine(
        f"mysql+pymysql://{config['user']}:{config['password']}@{config['host']}:{config['port']}/{config['database']}"
    )

# Load all users from the database
def load_users_mysql():
    engine = get_engine()
    with engine.connect() as conn:
        query = text("SELECT * FROM Users")
        df = pd.read_sql(query, conn)  # Use SQLAlchemy connection
        df['email'] = df['email'].str.lower().str.strip()
        df['phone'] = df['phone'].astype(str).str.strip()
    return df

# Load all phones from the database
def load_phones_mysql():
    engine = get_engine()
    with engine.connect() as conn:
        query = text("SELECT * FROM Phones")
        df = pd.read_sql(query, conn)  # Use SQLAlchemy connection
    return df

# Load sold phones from the database
def load_sold_mysql():
    engine = get_engine()
    with engine.connect() as conn:
        query = """
    SELECT P.*, U.address
    FROM Phones P
    JOIN Users U ON P.buyer_email = U.email
    WHERE P.status = 'Sold'
"""
        df = pd.read_sql(query, conn)  # Use SQLAlchemy connection
    return df

# Save a new phone to the database
def save_new_phone_mysql(data):
    engine = get_engine()
    with engine.connect() as conn:
        query = text("""
            INSERT INTO Phones (model, specs, `condition`, price, video1, status, buyer_email, buyer_phone, booking_time, payment_status)
            VALUES (:model, :specs, :condition, :price, :video1, :status, :buyer_email, :buyer_phone, :booking_time, :payment_status)
        """)
        conn.execute(query, data)

# Update phone details in the database
def update_phone_mysql(phone_id, updates):
    print("Called update_phone_mysql")  # Debug: Check if this function is called
    engine = get_engine()
    with engine.connect() as conn:
        with conn.begin():  # Begin a transaction
            # Dynamically construct the SET clause of the SQL query
            set_clause = ", ".join([f"{key} = :{key}" for key in updates.keys()])
            query = text(f"UPDATE Phones SET {set_clause} WHERE id = :id")  # Wrap query in text()
            updates["id"] = phone_id  # Add phone_id to the updates dictionary
            conn.execute(query, updates)  # Execute the query with parameters


# Login user by verifying email and password
def login_user_mysql(email, password):
    engine = get_engine()
    with engine.connect() as conn:  # Use SQLAlchemy's connection
        query = text("SELECT * FROM Users WHERE email = :email AND password = :password")  # Use text()
        result = conn.execute(query, {"email": email, "password": password})  # Execute with parameters
        user = result.fetchone()  # Fetch one row
        if user:
            # Map the result to a dictionary using column names
            return dict(zip(result.keys(), user))
        else:
            return None
        
def get_connection():
    return mysql.connector.connect(**config)

def signup_user_mysql(email, password, phone, address):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO Users (email, password, phone, address) VALUES (%s, %s, %s, %s)", (email, password, phone, address))
    conn.commit()
    cursor.close()
    conn.close()

def reset_password_mysql(email, phone, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET password = %s WHERE email = %s AND phone = %s", (new_password, email, phone))
    conn.commit()
    cursor.close()
    conn.close()

# --- App Setup ---
st.set_page_config(page_title="Mobile Store", layout="wide")
st.title("📱 Walker Wireless")

if "user" not in st.session_state:
    st.session_state.user = None

# --- Login and Signup ---
if st.session_state.user is None:
    tab1, tab2, tab3 = st.tabs(["Login", "Signup", "Reset password"])

    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            user = login_user_mysql(email, password)
            if user is not None:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Invalid email or password")

    with tab2:
        email = st.text_input("Signup Email", key="signup_email")
        phone = st.text_input("Phone Number", key="signup_phone", placeholder="e.g. 923001234567")
        password = st.text_input("Password", type="password", key="signup_password")
        address = st.text_input("Address", type="default", key="signup_address", placeholder="Please enter complete address")
        if st.button("Signup"):
            # Load existing users
            users = load_users_mysql()
            # Check if email or phone already exists
            if not users[users['email'] == email].empty:
                st.error("Email already exists. Please use a different email.")
            elif not users[users['phone'] == phone].empty:
                st.error("Phone number already exists. Please use a different phone number.")
            else:
                # Add new user to Google Sheets
                signup_user_mysql(email, password, phone, address)
                st.success("Signup successful! Please login.")
    with tab3:
        email = st.text_input("Email", key="reset_email")
        phone = st.text_input("Phone Number", key="reset_phone")
        password = st.text_input("New Password", type="password", key="reset_password")
        
        if st.button("Reset Password"):
            users = load_users_mysql()
            # st.write(users)  # Debug: Display the users DataFrame
            users['email'] = users['email'].str.lower().str.strip()  # Normalize email
            users['phone'] = users['phone'].astype(str).str.strip()  # Normalize phone
            email = email.lower().strip()  # Normalize input email
            phone = phone.strip()  # Normalize input phone
            user = users[(users['email'] == email) & (users['phone'] == phone)]  # Check both email and phone
            if not user.empty:
                new_password = password  # Use the provided new password
                idx = user.index[0]  # Get the index of the matching user
                reset_password_mysql(email, phone, new_password)
                st.success(f"Password reset successful! Your new password is: {new_password}")
            else:
                st.error("Email and phone number do not match. Please try again.")
else:
    user = st.session_state.user
    is_admin = user['email'] == 'admin'
    st.success(f"Logged in as {user['email']}")

    phones = load_phones_mysql()

    if is_admin:
        menu = st.sidebar.selectbox("Menu", ["Available Phones", "Booked", "Sold Phones", "Add new Phones"])
    else:
        menu = st.sidebar.selectbox("Menu", ["Available Phones", "Booked", "Purchased"])

    if menu == "Booked":
        if is_admin:
            if st.button("Refresh"):
                st.rerun()
                st.success("Phones refreshed!")            
            st.header("📦 Verify Payments for Phones")
            sold = phones[phones['status'] == 'Verification pending']

            for _, row in sold.iterrows():
                st.markdown(f"### Phone ID: {row['id']} - {row['model']}")
                new_status = st.selectbox(
                    f"Update Status for Phone ID {row['id']}",
                    options=["Verification pending", "Sold", "Rejected"],
                    index=["Verification pending", "Sold", "Rejected"].index(row['status']),
                    key=f"status_{row['id']}"
                )
                if new_status == "Sold":
                    status = "Sold"
                    paymentstatus = "Paid"
                    selling_time = datetime.now()
                elif new_status == "Rejected":
                    status = "available"
                    paymentstatus = ""
                    buyer_email = ""
                    buyer_phone = ""
                    booking_time = ""

                elif new_status == "Verification pending":
                    status = "Verification pending"
                    paymentstatus = "Pending"

                if st.button(f"Update Phone ID {row['id']}"):
                    if new_status == "Rejected":
                        update_phone_mysql(int(row['id']), {
                            'status': status,
                            'buyer_email': buyer_email,
                            'buyer_phone': buyer_phone,
                            'booking_time': booking_time,
                            'payment_status': paymentstatus
                        })
                    else:
                        update_phone_mysql(int(row['id']), {
                            'status': status,
                            'payment_status': paymentstatus,
                            'selling_time': selling_time

                        })
                    st.success(f"Phone ID {row['id']} updated successfully!")
                    time.sleep(5)
                    st.rerun()
        else:
            st.header("📋 Phones You Have Booked")
            timer_placeholder = st.empty()  # Create a placeholder for the timer
            if not phones[phones['buyer_email'] == user['email']]['booking_time'].empty:
                booking_time = pd.to_datetime(phones[phones['buyer_email'] == user['email']]['booking_time'].values[0])
                phone_status = phones[phones['buyer_email'] == user['email']]['status'].values[0]
                now = datetime.now()
                time_remaining = booking_time + timedelta(minutes=5) - now
                if phone_status == 'Booked':
                    if time_remaining.total_seconds() > 0:
                        minutes, secs = divmod(time_remaining.total_seconds(), 60)
                        timer_placeholder.markdown(f"**Time remaining: {int(minutes):02d}:{int(secs):02d}**")
                    else:
                        timer_placeholder.markdown("**Time's up!**")
                        # Update the phone status to available
                        update_phone_mysql(int(phones[phones['buyer_email'] == user['email']]['id'].values[0]), {
                            'status': 'available',
                            'buyer_email': '',
                            'buyer_phone': '',
                            'booking_time': '',
                            'payment_status': '',
                            'selling_time': ''
                        })
                        st.success(f"Booking expired for {(phones['model']['id'].values[0])}. Phone is now available.")
                        time.sleep(5)
                        st.rerun()
            # else:
            #     st.info("No active bookings found.")
            
            if st.button("Refresh"):
                st.rerun()
                st.success("Phones refreshed!")     

            Booked_phones = phones[(phones['buyer_email'] == user['email']) & ((phones['status'] == 'Booked') | (phones['status'] == 'Verification pending'))]
            only_booked = phones[(phones['buyer_email'] == user['email']) & ((phones['status'] == 'Booked'))]

            if not Booked_phones.empty:
                for _, phone in Booked_phones.iterrows():
                    with st.expander(f"{phone['model']} - Rs. {phone['price']}"):
                        st.markdown(f"**Specs:** {phone['specs']}")
                        st.markdown(f"**Condition:** {phone['condition']}")
                        st.markdown(f"**Booking Time:** {phone['booking_time']}")
                        st.markdown(f"**Payment status:** {phone['payment_status']}")

                        if st.button(f"Cancel Booking for {phone['model']}", key=f"cancel_{phone['id']}"):
                            try:
                                update_phone_mysql(int(phone['id']), {
                                    'status': 'available',
                                    'buyer_email': '',
                                    'buyer_phone': '',
                                    'booking_time': '',
                                    'payment_status': '',
                                    'selling_time': ''
                                })
                                st.success("Booking cancelled for {phone['model']}", key=f"cancel_{phone['id']}. Phone is now available.")
                                time.sleep(5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error cancelling booking: {e}")                                
                        # else:
                        #     if st.button(f"Confirm Cancel Booking for {phone['model']}", key=f"confirm_cancel_{phone['id']}"):
                        #         print("Clicked on confirm cancel booking")  # Debug: Check if this button is clicked
                        #         try:
                        #             update_phone_mysql(int(phone['id']), {
                        #                 'status': 'available',
                        #                 'buyer_email': '',
                        #                 'buyer_phone': '',
                        #                 'booking_time': '',
                        #                 'payment_status': '',
                        #                 'selling_time': ''
                        #             })
                        #             st.success("Booking cancelled. Phone is now available.")
                        #             time.sleep(5)
                        #             st.rerun()
                        #         except Exception as e:
                        #             st.error(f"Error cancelling booking: {e}")
                        #     elif st.button(f"Cancel Cancellation for {phone['model']}", key=f"cancel_cancellation_{phone['id']}"):
                        #         st.session_state[f"cancel_{phone['id']}"] = False
                        #         st.warning("Booking cancellation cancelled.")
                        #         time.sleep(5)
                        #         st.rerun()
            else:
                st.info("You have not Booked any phones.")

    elif menu == "Purchased":
        st.header("🛒 Phones You Have Purchased")
        if st.button("Refresh"):
            st.rerun()
            st.success("Phones refreshed!")
        purchased_phones = phones[(phones['buyer_email'] == user['email']) & (phones['status'] == 'Sold')]

        if not purchased_phones.empty:
            for _, phone in purchased_phones.iterrows():
                with st.expander(f"{phone['model']} - Rs. {phone['price']}"):
                    st.markdown(f"**Specs:** {phone['specs']}")
                    st.markdown(f"**Condition:** {phone['condition']}")
                    st.markdown(f"**Purchase Time:** {phone['booking_time']}")
                    st.markdown(f"**payment_status:** {phone['payment_status']}")
        else:
            st.info("You have not purchased any phones.")

    elif menu == "Add new Phones":
        st.header("📤 Admin: Add New Phone")
        with st.form("add_phone"):
            model = st.text_input("Phone Model", key="model")
            specs = st.text_area("Specifications", key="specs")
            condition = st.selectbox("Condition", ["New", "Used"], key="condition")
            price = st.number_input("Price (PKR)", min_value=1000, key="price")
            video1 = st.text_input("Video URL", key="video1")
            submitted = st.form_submit_button("Add Phone")
            if submitted:
                new_data = [model, specs, condition, price, video1, "available", "", "", "", ""]
                save_new_phone_mysql(new_data)
                st.success("Phone added successfully!")

    elif menu == "Sold Phones":
        st.header("📦 Sold Phones")
        if st.button("Refresh"):
            st.rerun()
            st.success("Phones refreshed!")
        sold_phones = load_sold_mysql()
        print(sold_phones)  # Debug: Display the sold phones DataFrame
        # sold_phones = phones[phones['status'] == 'Sold']

        for _, phone in sold_phones.iterrows():
            with st.expander(f"{phone['model']} - Rs. {phone['price']}"):
                st.markdown(f"**Specs:** {phone['specs']}")
                st.markdown(f"**Condition:** {phone['condition']}")
                st.markdown(f"**Sold Time:** {phone['booking_time']}")
                st.markdown(f"**Payment status:** {phone['payment_status']}")
                st.markdown(f"**Buyer Address:** {phone['address']}")

    else:  # Default to "Available Phones"
        st.header("📱 Available Phones")
        if st.button("Refresh"):
            st.rerun()
            st.success("Phones refreshed!")
        Available_phones = phones[phones['status'] == 'available']

        for _, phone in Available_phones.iterrows():
            with st.expander(f"{phone['model']} - Rs. {phone['price']}"):
                for media_url in [phone['video1']]:
                    if media_url.endswith(('.mp4', '.webm', '.ogg')):
                        st.markdown(
                            f"""
                            <video width="400" height="300" controls>
                                <source src="{media_url}" type="video/mp4">
                                Your browser does not support the video tag.
                            </video>
                            """,
                            unsafe_allow_html=True
                        )
                    elif media_url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                        st.image(media_url, width=200)
                    else:
                        st.warning(f"Unsupported media type: {media_url}")

                st.markdown(f"**Specs:** {phone['specs']}")
                st.markdown(f"**Condition:** {phone['condition']}")
                if st.button(f"Book {phone['model']}", key=phone['id']):
                    now = datetime.now()
                    update_phone_mysql(int(phone['id']), {
                        'status': 'Booked',
                        'buyer_email': user['email'],
                        'buyer_phone': user['phone'],
                        'booking_time': now
                    })

                    st.success("Phone Booked. Please pay 5000 PKR and confirm receipt within 5 minutes.")
                    time.sleep(5)  # Wait for 2 seconds before refreshing
                    st.rerun()

    # st.header("📤 Payment confirm")
    Booked_phones = phones[(phones['buyer_email'] == user['email']) & (phones['status'] == 'Booked')]

    for _, phone in Booked_phones.iterrows():
        if st.button(f"Confirm payment for {phone['model']}, Rs. {phone['price']}"):
            update_phone_mysql(int(phone['id']), {
                'payment_status': 'Pending',
                'status': 'Verification pending'
            })
            st.success("Payment submited for review")
            time.sleep(5)
            st.rerun()


    if st.button("Logout"):
        st.session_state.user = None
        time.sleep(5)
        st.rerun()
