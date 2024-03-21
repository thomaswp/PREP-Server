# PREP-Server

**Programming Replication Experiments Protocol (PREP)** is a *draft* protocol for designing interventions that occur during programming practice, which can be run across different practice environments. Currently support practice environments include:
* Visual Studio Code
* PCRS (University of Toronto)
* Snap (partial, in progress)
* 

The PREP-Server is an example server that implements PREP, and includes additional features to aid in the development of interventions:
* Built-in logging in ProgSnap2 format.
* Conditional assignment, including support for switching replications designs.
* The ability to build and update data-driven models on the fly as student submissions come in.

For a more advanced example of a PREP intervention, [see SimpleAIF](https://github.com/thomaswp/SimpleAIF).

## Setup

It is suggested to use VSCode to load this repository and a [virtual environment](https://code.visualstudio.com/docs/python/environments) to manage and install dependencies.

Take the following steps to install the PREP-Server.

1. Clone the repo with submodules (add the `--recursive` flag).
```bash
git clone --recursive https://github.ncsu.edu/HINTSLab/SimpleAIF.git
```
   * If you forget the recursive flag, run `git submodule update --init` after cloning.
2. Setup a python 3.9 (or greater) environment. On Windows this is easiest using [VS Code](https://code.visualstudio.com/docs/python/environments) (you will need to [use CMD](https://code.visualstudio.com/docs/terminal/profiles) rather than Powershell for your termnial) or [Anaconda](https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#activating-an-environment), and on Unix pyenv.
3. Install the dependencies using the included ``requirements.txt`` file.
```bash
pip install -r requirements.txt
```
4. Copy `server/config.example.yaml` to `server/config.yaml` and update it to your need based on the comments.


## Serving Feedback

You can run the server using the code found in the server folder.
1. Run ``main.py``. It should start a server on port 5500.
   * If the server fails to start, make sure you're running it from the correct directory (the server directory).

Use a PREP-supporting client to interact with the server.

### Building a Model On the Fly or Using a Custom Dataset via HTTP Post

If your dataset is not in ProgSnap2 format, or you do not have prior data, you can still use data-driven models. You can use the following steps to populate a new ProgSnap2 database and build the model, either as students submit their work, and/or with seed data you already have available.

1) Run `main.py` to start the server (see instructions above).
2) Add relevant data, with a call similar to the below:

```python
url = f"http://127.0.0.1:5500/{row[PS2.EventType]}/"
x = requests.post(url, json = row_dict)
```

Where the `row_dic` is an object with key-value pairs matching the fields described in the next section.

#### Student Attempts at a Problem

SimpleAIF is a data-driven model, and it requires some data from prior students to provide feedback. Ideally, this data is available for some or all problems beforehand (even if generated by an instructor), but if not it can be added at runtime.

Either way, send an HTTP-POST request to `http://127.0.0.1:5500/XXX/`, where XXX is one of the following ProgSnap2 EventTypes (they will have the same result):
* `Submit`
* `FileEdit`
* `Run.Program`

The request should at a minimum have the following JSON in the post body:
* `ProblemID`: The problem ID (e.g., `32` or `sum_of_three`).
* `SubjectID`: The user ID (e.g., `123` or `student_1`). **Note** that this ID will be stored in the local database, so if desired you can hash/encrypt it before sending it to the server. Ideally, SubjectIDs should remain consistent across problems, though this is not strictly necessary for SimpleAIF.
* `CodeState`: The student's current code at the time of the event (e.g., `def foo():\n\treturn 0`).
* `Score`: The score for the student's current code, ranging from 0-1, where 1 indicates fully correct code. This can be assessed automatically (e.g., by test cases) or manually if using previously collected data.
* `NoLogging` [Optional]: This can be set to `false` to tell SimpleAIF not to record the event.

The request can also include the following, though they are not currently used by SimpleAIF:
* `AssignmentID`: A unique ID for the assignment that this problem belongs to (e.g., `hw1` or `lab2`).
* `ClientTimestamp`: The time of the event according to the client in ISO format (e.g., `2021-11-08T15:00:00Z`).
* `ServerTimestamp`: The time of the event according to the server in ISO format (e.g., `2021-11-08T15:00:00Z`).

For example, the JSON request might look like:
```
{
    "ProblemID": "8",
    "SubjectID": "Student01",
    "CodeState": "def collect_underpreforme",
    "Score": 0
    "ShouldLog": true,
    "AssignmentID": "Assignment01",
    "ClientTimestamp": "2023-10-20T19:14:29.692Z",
}
```

Note that currently SimpleAIF will build a feedback model for a given problem when it has at least `MIN_CORRECT_COUNT_FOR_FEEDBACK` correct student responses for that problem. It will subsequently recompile the models if it receives an additional `COMPILE_INCREMENT` correct responses. These values are set in `main.py`.

For example, if `MIN_CORRECT_COUNT_FOR_FEEDBACK` is 10 and `COMPILE_INCREMENT` is 5, SimpleAIF will build a model after 10 correct responses, and then rebuild it after 15, 20, 25, etc. correct responses.

## Deploying the server in production

### Optaining an SSL Certificate

Before you begin, you should decide whether and how to obtain an SSL certificate, in order to serve over HTTPs. This is necessary for the client to access the server from most modern browsers and is recommended for security reasons.

The easiest way to obtain a certificate is through [Let's Encrypt](https://letsencrypt.org/)'s Certbot. You can follow the instructions [here](https://letsencrypt.org/getting-started/) to obtain a certificate using Certbot. You will need to have a domain name pointing to your server's IP address.

For the following steps, you will need to know where your certificate files are located. If use Let's Encrypt's Certbot, they will be in `/etc/letsencrypt/live/<domain_name>/`.

**You will then need to copy these files to this folder**:
```bash
cp /etc/letsencrypt/live/<domain_name>/fullchain.pem ssl/
cp /etc/letsencrypt/live/<domain_name>/privkey.pem ssl/
```

**Note**: You will need to repeat this process each time the certificate is renewed. An alternative is to use a symlink:
```bash
ln -s /etc/letsencrypt/live/<domain_name>/fullchain.pem ssl/fullchain.pem
ln -s /etc/letsencrypt/live/<domain_name>/privkey.pem ssl/privkey.pem
```

If you chose *not* to use SSL, you may need to change the final CMD in the Doockerfile to omit the `--certfile` and `--keyfile` arguments.

### Building with Docker

**Note**: Before deploying, make sure your have followed the checklist below to make sure everything is up to date.

The default Flask app is not meant to be run in production. To run it in production, take the following steps:

1. Install [Docker](https://docs.docker.com/get-docker/)
2. Build the Docker image
```bash
docker build -t simple_aif .
```
3. Run the Docker image, using this command and replacing `<port>` with your desired port, and `<path-on-server>` with the absolute path to the SimpleAIF repository you are working in. Make sure your client uses the same port and that the port is open and forwarded.
```bash
docker run -p <port>:80  -v /<path-on-server>/SimpleAIF/server/data:/app/server/data simple_aif
```
  * **Note**: Mapping the data folder is necessary to persist the database between runs. Otherwise it will be **deleted** when the container is stopped.
  * **Note**: If serving HTTPS content, you should use port 443 instead of 80.
4. Verify that the server is running by visiting `http://localhost:<port>/` in your browser. You should see a message like `Hello, world!`.
5. Verify that `server/data/Logging.db` has been created. This may require you to use the server.

To stop the server, run `docker ps` to get the container ID, and then `docker stop <container_id>`.
