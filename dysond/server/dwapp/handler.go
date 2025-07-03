package dwapp

import (
	"bufio"
	"bytes"
	"encoding/base64"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	"github.com/cosmos/cosmos-sdk/client"

	scriptv1 "dysonprotocol.com/x/script/types"
)

const (
	txtRecordKey = "DYS_DWAPP"
)

func NewDefaultHandler(clientCtx client.Context, ScriptAddressOrNamePattern string) http.Handler {
	fmt.Println("ScriptAddressOrNamePattern: ", ScriptAddressOrNamePattern)
	scriptAddressOrNameRe := regexp.MustCompile(ScriptAddressOrNamePattern)
	return &DefaultHandler{
		clientCtx:             clientCtx,
		scriptAddressOrNameRe: scriptAddressOrNameRe,
	}
}

type DefaultHandler struct {
	clientCtx             client.Context
	scriptAddressOrNameRe *regexp.Regexp
}

func (h *DefaultHandler) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	var addressOrName string

	// First, try to get address from TXT records
	txtRecords, err := getTXTRecords(req.Host)
	if err == nil && txtRecords != nil {
		if txtAddressOrName, ok := txtRecords[txtRecordKey]; ok && txtAddressOrName != "" {
			addressOrName = txtAddressOrName
			fmt.Printf("Found address from TXT record: %s\n", addressOrName)
		}
	}

	// If no address found in TXT records, fall back to regex pattern matching
	if addressOrName == "" {
		// split the host and use the first part as the address
		match := h.scriptAddressOrNameRe.FindStringSubmatch(req.Host)

		if len(match) <= 1 {
			errorMsg := fmt.Sprintf("No address found for host: `%s` using ScriptAddressOrNamePattern: `%s`  match: %v", req.Host, h.scriptAddressOrNameRe.String(), match)
			http.Error(w, errorMsg, http.StatusNotFound)
			return
		} else {
			addressOrName = match[1]
			fmt.Printf("Found address from regex pattern: %s\n", addressOrName)
		}
	}

	// get the raw request
	rawRequest, err := getRawRequest(req)
	if err != nil {
		http.Error(w, "Error getting raw request", http.StatusInternalServerError)
		return
	}

	fmt.Println("rawRequest: ", rawRequest)

	// Create the request
	queryReq := &scriptv1.WebRequest{
		AddressOrName: addressOrName,
		Httprequest:   rawRequest,
	}

	// Create a response object
	resp := &scriptv1.WebResponse{}

	// Use clientCtx.Invoke instead of direct app.Query
	err = h.clientCtx.Invoke(req.Context(), "/dysonprotocol.script.v1.Query/Web", queryReq, resp)
	if err != nil {
		fmt.Println("[ERROR] DWApp Handler: Error querying app:", err)
		http.Error(w, fmt.Sprintf("Error querying: %v", err), http.StatusInternalServerError)
		return
	}

	// get the last line
	lines := strings.Split(resp.Httpresponse, "\n")
	lastLine := lines[len(lines)-1]

	decoded, err := base64.StdEncoding.DecodeString(lastLine)
	if err != nil {
		fmt.Println("[ERROR] DWApp Handler: Error decoding response:", err)
		http.Error(w, "Error decoding", http.StatusInternalServerError)
		return
	}

	// write the response directly to the writer
	err = WriteRawResponse(decoded, w)

	if err != nil {
		fmt.Println("[ERROR] DWApp Handler: Error writing response:", err)
		http.Error(w, fmt.Sprintf("Error writing response: %v", err), http.StatusInternalServerError)
		return
	}
}

func WriteRawResponse(rawResponse []byte, w http.ResponseWriter) error {
	// Convert bytes to a buffered reader for easier line-by-line reading
	reader := bufio.NewReader(bytes.NewReader(rawResponse))

	// Read the status line
	statusLine, err := reader.ReadString('\n')
	if err != nil {
		return fmt.Errorf("failed to read status line: %v, %s", err, rawResponse)
	}
	fmt.Println("statusLine: ", statusLine)
	statusLine = strings.TrimSpace(statusLine) // Remove any trailing whitespace

	// Parse the status line
	parts := strings.SplitN(statusLine, " ", 3)
	if len(parts) < 2 {
		return fmt.Errorf("malformed status line: '%s'", statusLine)
	}
	fmt.Println("parts: ", parts)
	statusCode, err := strconv.Atoi(parts[1])
	if err != nil {
		return fmt.Errorf("invalid status code: %v", err)
	}

	// Read and set headers
	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			return fmt.Errorf("failed to read header line: %v", err)
		}
		fmt.Println("line: ", line)
		line = strings.TrimSpace(line)
		if line == "" {
			break // Headers section has ended
		}

		parts := strings.SplitN(line, ": ", 2)
		if len(parts) != 2 {
			return fmt.Errorf("malformed header: '%s'", line)
		}
		fmt.Println("parts: ", parts)
		w.Header().Add(parts[0], parts[1])
	}
	fmt.Println("statusCode: ", statusCode)

	// Set the status code
	w.WriteHeader(statusCode)

	// Write the body
	for {
		buffer := make([]byte, 1024)
		n, err := reader.Read(buffer)
		if err != nil && err.Error() != "EOF" {
			return fmt.Errorf("failed to read body: %v", err)
		}
		if n == 0 {
			break
		}
		_, err = w.Write(buffer[:n])
		if err != nil {
			return fmt.Errorf("failed to write body: %v", err)
		}
	}

	return nil
}

func getRawRequest(r *http.Request) (string, error) {
	var buf bytes.Buffer

	// Write the request method, URL, and protocol
	if _, err := fmt.Fprintf(&buf, "%s %s %s\r\n", r.Method, r.URL.RequestURI(), r.Proto); err != nil {
		return "", err
	}

	// Write the headers
	for k, vs := range r.Header {
		for _, v := range vs {
			if _, err := fmt.Fprintf(&buf, "%s: %s\r\n", k, v); err != nil {
				return "", err
			}
		}
	}

	// Write an extra CRLF to indicate the end of headers
	if _, err := fmt.Fprint(&buf, "\r\n"); err != nil {
		return "", err
	}

	// If there's a body, write it to the buffer
	if r.Body != nil {
		bodyBytes := new(bytes.Buffer)
		if _, err := bodyBytes.ReadFrom(r.Body); err != nil {
			return "", err
		}
		if _, err := buf.Write(bodyBytes.Bytes()); err != nil {
			return "", err
		}
		// IMPORTANT: Restore the body to the request object
		r.Body = io.NopCloser(bytes.NewBuffer(bodyBytes.Bytes()))
	}

	return buf.String(), nil
}

// getTXTRecords queries DNS TXT records for a domain and looks for dyson= entries
func getTXTRecords(host string) (map[string]string, error) {
	// Remove port if present
	domain, _, err := net.SplitHostPort(host)
	if err != nil {
		// If error, assume no port was present
		domain = host
	}

	// Query TXT records
	txtRecords, err := net.LookupTXT(domain)
	if err != nil {
		return nil, err
	}

	// Look for dyson= in TXT records
	for _, txt := range txtRecords {
		if strings.Contains(txt, txtRecordKey+"=") {
			// Parse the TXT record as URL query parameters
			values, err := url.ParseQuery(txt)
			if err != nil {
				continue
			}

			// Convert url.Values to map[string]string
			result := make(map[string]string)
			for k, v := range values {
				if len(v) > 0 {
					result[k] = v[0]
				}
			}

			// If dyson key exists, return the map
			if _, ok := result[txtRecordKey]; ok {
				return result, nil
			}
		}
	}

	return nil, nil
}
