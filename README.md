Team Project 1 of System Software Analysis at Ivy Tech Community College. Members are: Mark Ciesiolka, William Clayton, Zachary Collins, Cody Gunter, Duncan Hegerman, and Abigail Huijon.

To start the Django environment, you will need VS Code. Clone the repository to a directory of your choosing, then open the directory via "File" > "Open Folder".

1: Once you are in the repository in VS Code, you will need to implement a virtual environment (.venv). To do this, open a terminal then type "py -m venv .venv".

2: Activate the virtual environment: ".venv/Scripts/activate"

3: Installing and upgrading dependencies: "python -m pip install --upgrade pip", then when that is done, "python -m pip install -r requirements.txt"

4: Preparing database: "python manage.py migrate"

5: Finally, starting the Django server: "python manage.py runserver". 

After you start the server, the application can be accessed at "http://127.0.0.1:8000" (port 8000 is default). 
