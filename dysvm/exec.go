package dysvm

import (
	"fmt"
	"strings"

	"dysonprotocol.com/dysvm/internal/data"

	"github.com/kluctl/go-embed-python/embed_util"
	"github.com/kluctl/go-embed-python/python"
)

func Exec(msgJSON, scriptJSON, attachedMsgResultsJSON, headerInfoJSON, port string) (string, error) {
	var lib *embed_util.EmbeddedFiles
	ep, err := python.NewEmbeddedPython("dyslang")
	if err != nil {
		return "", err
	}

	lib, err = embed_util.NewEmbeddedFiles(data.Data, "dyslang-libs")

	if err != nil {
		return "", err
	}
	// TODO Make this an environment variable or config
	ep.AddPythonPath("./dysvm/internal/py-dyslang")
	ep.AddPythonPath(lib.GetExtractedPath())

	cmd, err := ep.PythonCmd("-m", "dyslang", "exec_script", msgJSON, scriptJSON, attachedMsgResultsJSON, headerInfoJSON, port)

	if err != nil {
		return "", err
	}

	out, runErr := cmd.CombinedOutput()

	return string(out), runErr

}

func Benchmark(iterations int, details bool) (string, error) {
	var lib *embed_util.EmbeddedFiles
	ep, err := python.NewEmbeddedPython("dyslang")
	if err != nil {
		return "", err
	}

	lib, err = embed_util.NewEmbeddedFiles(data.Data, "dyslang-libs")
	if err != nil {
		return "", err
	}

	// TODO Make this an environment variable or config
	ep.AddPythonPath("./dysvm/internal/py-dyslang")
	ep.AddPythonPath(lib.GetExtractedPath())

	var detailsFlag string
	if details {
		detailsFlag = "true"
	} else {
		detailsFlag = "false"
	}

	cmd, err := ep.PythonCmd("-m", "dyslang", "run_benchmark", fmt.Sprintf("%d", iterations), detailsFlag)
	if err != nil {
		return "", err
	}

	out, runErr := cmd.CombinedOutput()

	return string(out), runErr
}

func Wsgi(port, scriptName, scriptJSON, blockInfoJSON, httpreq string) (string, error) {
	var lib *embed_util.EmbeddedFiles
	ep, err := python.NewEmbeddedPython("dyslang")
	if err != nil {
		return "", err
	}

	lib, err = embed_util.NewEmbeddedFiles(data.Data, "dyslang-libs")

	if err != nil {
		return "", err
	}
	// TODO Make this an environment variable or config
	ep.AddPythonPath("./dysvm/internal/py-dyslang")
	ep.AddPythonPath(lib.GetExtractedPath())

	cmd, err := ep.PythonCmd("-m", "dyslang", "run_wsgi", port, scriptName, scriptJSON, blockInfoJSON, httpreq)

	if err != nil {
		return "", err
	}

	out, runErr := cmd.CombinedOutput()

	fmt.Println("Command output: ", string(out))
	fmt.Println("Command error: ", runErr)

	return string(out), runErr

}

func DysFormat(code string) (string, error) {
	var lib *embed_util.EmbeddedFiles
	ep, err := python.NewEmbeddedPython("dyslang")
	if err != nil {
		return "", err
	}

	lib, err = embed_util.NewEmbeddedFiles(data.Data, "dyslang-libs")
	if err != nil {
		return "", err
	}

	// TODO Make this an environment variable or config
	ep.AddPythonPath("./dysvm/internal/py-dyslang")
	ep.AddPythonPath(lib.GetExtractedPath())

	cmd, err := ep.PythonCmd("-m", "dyslang", "dys_format")
	if err != nil {
		return "", err
	}

	// Set stdin to the code
	cmd.Stdin = strings.NewReader(code)

	out, runErr := cmd.Output()
	if runErr != nil {
		return "", fmt.Errorf("failed to format code: %w, %s", runErr, string(out))
	}

	return string(out), nil
}
