```javascript
const fileInput = document.getElementById("fileInput");
const fileName = document.getElementById("fileName");


// FILE UPLOAD
fileInput.addEventListener("change", function () {

    if (this.files.length > 0) {

        fileName.textContent =
            "Selected: " + this.files[0].name;

    }

});


// SCROLL TO ANALYZER
function scrollToAnalyzer() {

    document
        .getElementById("analyzer")
        .scrollIntoView({
            behavior: "smooth"
        });

}


// DEMO
function showDemo() {

    alert(
        "Demo Flow:\n\n" +
        "1. Upload server error log\n" +
        "2. AI analyzes the error\n" +
        "3. AI generates a patch\n" +
        "4. Patch runs inside E2B Sandbox\n" +
        "5. Tests verify the patch"
    );

}


// ANALYZE ERROR
function analyzeError() {

    if (fileInput.files.length === 0) {

        alert("Please upload an error log first.");

        return;
    }


    const result =
        document.getElementById("analysisResult");


    result.innerHTML = `

        <div class="analysis-data">

            <p>
                <strong>Error:</strong>
                <span>NullPointerException</span>
            </p>

            <p>
                <strong>File:</strong>
                <span>PaymentService.java</span>
            </p>

            <p>
                <strong>Line:</strong>
                <span>142</span>
            </p>

            <p>
                <strong>Severity:</strong>
                <span>HIGH</span>
            </p>

            <p>
                <strong>Root Cause:</strong>
                Object accessed before initialization.
            </p>

            <p>
                <strong>AI Patch:</strong>
                Initialize the payment object before processing.
            </p>

        </div>

    `;


    startVerification();

}


// START VERIFICATION
function startVerification() {

    const status =
        document.getElementById("sandboxStatus");

    const badge =
        document.getElementById("statusBadge");

    const progress =
        document.getElementById("progressBar");

    const finalResult =
        document.getElementById("finalResult");


    finalResult.style.display = "none";


    status.textContent = "Creating Sandbox";

    badge.textContent = "● Running";

    badge.className = "status running";


    progress.style.width = "10%";


    setTimeout(() => {

        status.textContent = "Reproducing Error";

        progress.style.width = "35%";

        document.getElementById("test1").textContent = "✓";

        document.getElementById("test1").style.color =
            "#22c55e";

    }, 1000);


    setTimeout(() => {

        status.textContent = "Applying AI Patch";

        progress.style.width = "55%";

        document.getElementById("test2").textContent = "✓";

        document.getElementById("test2").style.color =
            "#22c55e";

    }, 2000);


    setTimeout(() => {

        status.textContent = "Running Tests";

        progress.style.width = "75%";

        document.getElementById("test3").textContent = "✓";

        document.getElementById("test3").style.color =
            "#22c55e";

    }, 3000);


    setTimeout(() => {

        status.textContent = "Verification Complete";

        progress.style.width = "100%";

        document.getElementById("test4").textContent = "✓";

        document.getElementById("test4").style.color =
            "#22c55e";


        badge.textContent = "● Verified";

        badge.className = "status verified";


        finalResult.style.display = "flex";


    }, 4000);

}
```
