# %% [markdown]
# # Cell 4: Task Benchmark
# 60 agentic tasks across 3 environments (20 per environment).
# Tasks are designed to test multi-turn state management, error recovery,
# and multi-hop reasoning within the D_max = 5 turn limit.

# %% Cell 4: Task Benchmark Dataset
def generate_benchmark():
    """Returns the complete 60-task evaluation benchmark.
    Each task is a multi-step objective requiring iterative agent interaction."""

    bash_tasks = [
        {"id": "bash_1", "task": "Create a nested directory 'project/src/lib'. Inside 'lib', create an empty file 'math.py'. Then, securely move 'math.py' to 'project/src/' and delete the 'lib' folder."},
        {"id": "bash_2", "task": "Write the phrase 'Agentic AI' into a file named 'ai.txt'. Use grep to extract the word 'AI' from it and redirect that specific output to 'result.txt'. Finally, read 'result.txt'."},
        {"id": "bash_3", "task": "Create three log files: 'app.log', 'db.log', and 'sys.bak'. Find all files ending in '.log', append the line 'ARCHIVED' to them, and move them into a new directory named 'archived_logs'."},
        {"id": "bash_4", "task": "Find the absolute path of the current working directory, save it to 'pwd.dat', then append the current username to the next line of 'pwd.dat'. Read the file to ensure it has two lines."},
        {"id": "bash_5", "task": "Create a file named 'secure.key'. Change its permissions so that only the owner can read and write to it. Verify the permissions using ls -l."},
        {"id": "bash_6", "task": "Write a bash script named 'loop.sh' that echoes the numbers 1 through 5. Make it executable, run it, and output the result to 'loop_out.txt'."},
        {"id": "bash_7", "task": "Create a directory named 'data'. Inside, create files 1.csv through 10.csv. Then, write a command to count exactly how many files exist in the 'data' directory and save that number to 'count.txt'."},
        {"id": "bash_8", "task": "Create a file 'base.txt' with the word 'Hello'. Copy it to 'copy.txt'. Append ' World' to 'copy.txt'. Display the differences between 'base.txt' and 'copy.txt' using diff."},
        {"id": "bash_9", "task": "Find all files in the current directory modified in the last 1 day. If any exist, list them in 'recent.list'."},
        {"id": "bash_10", "task": "Create a file 'sysinfo.txt'. Write the total available system memory (using free or similar) into it, and then append the total disk usage."},
        {"id": "bash_11", "task": "Write the string '1,2,3,4,5' into 'data.csv'. Use the cut or awk command to extract only the third column and save it to 'col3.txt'."},
        {"id": "bash_12", "task": "Create a file named 'readonly.txt', remove all write permissions from it, and then attempt to append data to it (which should fail). Catch the error or observe the failure."},
        {"id": "bash_13", "task": "List all running python processes. If there are none, echo 'No Python' to 'status.log'. Otherwise, echo 'Python Running' to 'status.log'."},
        {"id": "bash_14", "task": "Create a directory 'archive'. Compress an empty text file 'dummy.txt' into a tarball inside 'archive/' called 'dummy.tar.gz'. Verify the tarball exists."},
        {"id": "bash_15", "task": "Write a string 'apple\\nbanana\\napple\\ncherry' into 'fruits.txt'. Sort the file, remove duplicates using uniq, and save the result to 'unique_fruits.txt'."},
        {"id": "bash_16", "task": "Check whether a directory named 'foo' exists. If it does not, create it. Then, regardless of whether it existed, create 'foo/bar.txt'."},
        {"id": "bash_17", "task": "Find the word count of the file 'fruits.txt' (from task 15) using wc. Extract just the number of lines and save it to 'lines.txt'."},
        {"id": "bash_18", "task": "Create a file named '-hyphen_file.txt' (notice the leading dash). Add text to it, then figure out the proper bash syntax to delete a file that starts with a dash."},
        {"id": "bash_19", "task": "Use the seq command to generate numbers 1 to 100, use sed to replace 50 with 'HALF', and save the output to 'numbers.txt'."},
        {"id": "bash_20", "task": "Create a soft link to 'numbers.txt' named 'numbers_link.txt'. Verify that modifying the link modifies the original file."}
    ]

    python_tasks = [
        {"id": "py_1", "task": "Write a Python script that defines a class 'Bank' with a balance. Instantiate it with 100, withdraw 50, attempt to withdraw 100 (which must explicitly raise a ValueError), catch the error, and print 'Safe'."},
        {"id": "py_2", "task": "Write a script to generate a random 5x5 matrix using normal Python lists, find the maximum value, scale the entire matrix by that maximum, and calculate the trace (sum of diagonal). Print the trace."},
        {"id": "py_3", "task": "Create a script that takes the string 'Agentic Artificial Intelligence', builds a frequency dictionary of its letters (ignoring spaces), sorts it by highest frequency, and prints the top 3 characters."},
        {"id": "py_4", "task": "Write a program that implements a binary search tree (BST). Insert nodes [10, 5, 15, 2, 7], and write a function to return the explicitly ordered traversal of the tree. Print the list."},
        {"id": "py_5", "task": "Write a script that creates a JSON string containing a list of 3 users with names and ages. Parse the JSON, filter out users under 18, reserialize it, and print the output."},
        {"id": "py_6", "task": "Write a Python script that opens a file 'data.bin' in binary write mode, writes the byte sequence for 'Colab', closes it, reopens in read mode, decodes it, and prints passing if it matches."},
        {"id": "py_7", "task": "Implement the Sieve of Eratosthenes algorithm in Python to find all prime numbers up to 100. Write the resulting array of primes to 'primes.txt'."},
        {"id": "py_8", "task": "Write a function that calculates the Levenshtein distance between 'kitten' and 'sitting'. The function must not use external libraries. Print the integer distance."},
        {"id": "py_9", "task": "Write a Python program that uses multithreading to simulate downloading 3 files concurrently (using time.sleep). Ensure all threads join before printing 'Downloads Complete'."},
        {"id": "py_10", "task": "Create a Python script that generates 1000 random floating point numbers, calculates their standard deviation manually without importing the statistics or math module, and prints the result."},
        {"id": "py_11", "task": "Write a script that defines a decorator function `@timer` which measures the execution time of a function. Apply it to a function that sums range(10000) and execute it."},
        {"id": "py_12", "task": "Implement a Python script that scrapes its own source code (using __file__), counts the number of lines, and prints the count. Handle potential FileNotFounds gracefully."},
        {"id": "py_13", "task": "Write a Python script that uses a regular expression to extract all valid email addresses from the multiline string 'Contact us at info@example.com or admin@test.co.uk. Do not use test@.'. Print the matches."},
        {"id": "py_14", "task": "Create a generator function in Python that yields the infinite sequence of Fibonacci numbers. Iterate through the generator to print exactly the first 15 numbers, then break."},
        {"id": "py_15", "task": "Write a script that takes a list of dictionaries [{'k': 'a', 'v': 1}, {'k': 'b', 'v': 2}, {'k': 'a', 'v': 3}]. Group the dictionaries by 'k' and sum the 'v' values. Print the final dict."},
        {"id": "py_16", "task": "Create a Python script that simulates a simple state machine with states START, RUNNING, and END. Transition START->RUNNING automatically, then RUNNING->END after 1 loop. Print the state trace."},
        {"id": "py_17", "task": "Write a Python script to deeply merge two complex nested dictionaries: {'a': {'b': 1}}, {'a': {'c': 2}}. Do not use external libraries. Print the merged dictionary."},
        {"id": "py_18", "task": "Implement an explicit caching system (memoization) for a recursive factorial function using a standard Python dictionary. Show that calling factorial(10) twice retrieves the cached value the second time."},
        {"id": "py_19", "task": "Write a Python program that reads environment variables. If 'TEST_MODE' is not set, set it to '1' using os.environ, then retrieve it and print 'Test Mode Active'."},
        {"id": "py_20", "task": "Write a clean, recursive Python function that flattens an arbitrarily nested list (e.g., [1, [2, [3, 4], 5]]) into a single 1D list. Print the flattened output."}
    ]

    web_tasks = [
        {"id": "web_1", "task": "Search for the primary authors of the QLoRA paper published in 2023. Then, execute a second search on the lead author to find out what university they were affiliated with."},
        {"id": "web_2", "task": "Look up the exact parameter sizes of the Google Gemma 3 model family. Then, search for the parameter sizes of the Meta Llama 3.1 models. Output a comparison of which family has a ~8B class model."},
        {"id": "web_3", "task": "Search for the concept of 'Direct Preference Optimization' (DPO). Based on the results, run another search to find out which earlier reinforcement learning technique (RLHF) DPO was designed to replace."},
        {"id": "web_4", "task": "Find out the key architectural difference between LLaMA 2 and LLaMA 3. Specifically, search for how they handle Grouped Query Attention (GQA)."},
        {"id": "web_5", "task": "Search for the term 'Mixture of Experts' (MoE). Determine what gating mechanism MoE uses to select which expert network processes a given token."},
        {"id": "web_6", "task": "Find out what 'FlashAttention 2' improved over the original FlashAttention. Then, verify if the Qwen 3.5 architecture utilizes it natively."},
        {"id": "web_7", "task": "Search for the exact definition of the NF4 quantization datatype utilized by bitsandbytes. What distribution is it optimized for?"},
        {"id": "web_8", "task": "Investigate what the 'ReAct' testing framework evaluates. Find the original paper and summarize its two core components in a single sentence."},
        {"id": "web_9", "task": "Search for the context window length (in tokens) of the microsoft/phi-4-mini model. Compare that to the context window of Gemma-3-4b."},
        {"id": "web_10", "task": "Find out when Google Colab upgraded their free tier GPUs from T4 hardware. Are T4s still the primary free tier GPU?"},
        {"id": "web_11", "task": "Search for what the HuggingFace 'safetensors' format is and why it is more secure than traditional PyTorch 'bin' or 'pt' pickle files."},
        {"id": "web_12", "task": "Find out what 'Rotary Position Embeddings' (RoPE) are. Run a secondary search to find which foundational model first popularized them instead of absolute embeddings."},
        {"id": "web_13", "task": "Search for the difference between FP16, BF16, and INT8 compute types in deep learning inference. What does the 'B' in BF16 stand for?"},
        {"id": "web_14", "task": "Investigate the primary purpose of 'Speculative Decoding' in large language models. Does it affect the final output quality or just the speed?"},
        {"id": "web_15", "task": "Find out what the 'LMSys Chatbot Arena' is. Discover which model was ranked #1 on their leaderboard at the end of 2024."},
        {"id": "web_16", "task": "Search for what 'Continuous Batching' (or in-flight batching) means in the context of LLM inference servers like vLLM. Why does it improve throughput?"},
        {"id": "web_17", "task": "Determine what the 'System Prompt' does differently than a 'User Prompt' when interacting with a Chat-tuned model. How do chat templates format it?"},
        {"id": "web_18", "task": "Search the web to find out how the DeepSeek-R1 architecture differs fundamentally from standard auto-regressive models regarding chain-of-thought tokens."},
        {"id": "web_19", "task": "Find out why small models (under 10B parameters) struggle with 'Contextual Myopia' or forgetting system prompts over long conversations."},
        {"id": "web_20", "task": "Search for 'Model Collapse' in AI research. Run a subsequent search to find out if training models purely on synthetic data causes this phenomenon."}
    ]

    return {
        "Env_A_Bash": bash_tasks,
        "Env_B_Python": python_tasks,
        "Env_C_Web": web_tasks
    }
