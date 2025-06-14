# Extended Ubytec Schema

[![Codacy Badge](https://api.codacy.com/project/badge/Grade/3f97e874350447509cc84b2ff7990b0b)](https://app.codacy.com/gh/Universal-Byte-Code/schema?utm_source=github.com&utm_medium=referral&utm_content=Universal-Byte-Code/schema&utm_campaign=Badge_Grade)

This repository defines the **Extended Ubytec AST Schema**, providing a JSON Schema specification for representing ASTs (Abstract Syntax Trees) in the Ubytec language. It covers:

- **Root Sentence** (`RootSentence`), as the top-level container of nodes and child sentences.
- **Metadata** about the entire AST and its encoding/version info.
- **Syntax Nodes** (`SyntaxNode`) – each representing a logical construct like a block, loop, or conditional.
- **Tokens** (`SyntaxToken`) – the lexical info (source string, line/row/column).
- **Operations** (`Operation`) – the core logic, including normal opcodes (`0..254`) and extended opcodes (object form with `"OpCode": 255`).

---

## Highlights

1. **Root-Level Objects**
   - **`RootSentence`**  
     - Serves as the top-level container of the AST in Ubytec.  
     - Holds its own **metadata** plus the highest-level set of `Nodes` or nested sentences.  
     - Typically represents a full program, script, or module in source form.  
   - **`Metadata`**  
     - Stores global information about the AST, such as:  
       - **guid**: A unique identifier for the tree or file.  
       - **encoding**: The character encoding (e.g., UTF-8).  
       - **langver**: A string or version number indicating which variant or version of Ubytec this AST targets.  
     - Ensures tools and interpreters can handle the AST consistently across different environments or language revisions.

2. **SyntaxSentence**
   - Represents a logical grouping of syntax, akin to a code block or statement list.  
     - **Nodes** (`SyntaxNode`): An array of syntactic constructs (e.g., a single statement or an operation).  
     - **Sentences**: An array of **nested** `SyntaxSentence` objects, allowing deeper blocks or conditional sections (like nested IF statements, loops, etc.).  
     - **Metadata**: Contains fields like `guid` (unique to the sentence) and `type` (e.g., `"block"`, `"if"`, `"loop"`), helping to identify the purpose or category of this sentence.  
   - Ubytec compilers often walk this structure recursively to process each code block in the correct order.

3. **SyntaxNode**
   - The basic building block of the AST, often corresponding to a single operation, expression, or declaration.  
     - **Operation**: A required field describing the opcode or language construct (e.g., `IF`, `WHILE`, `BLOCK`).  
     - **Children**: An optional array of further `SyntaxNode` elements, used if the operation naturally contains subordinate statements or expressions. May be `null` if there are no child nodes.  
     - **Tokens**: An optional array of `SyntaxToken` for source-code correlation, or `null` if no direct tokens are attached.  
     - **Metadata**: Node-level details, such as a unique `guid`, partial assembly code references (`nasm`), or other node-specific data.

4. **Operation**
   - Specifies the **instruction or language feature** represented by this node.  
       - **`OpCode`**:  
         - If `0..254` (integer), it indicates a **standard** Ubytec opcode (like `BLOCK`, `LOOP`, `ADD`, etc.).  
         - If it’s an **object** with `{ "OpCode": 255, "ExtensionGroup": X, "ExtendedOpCode": Y }`, it represents an **extended** opcode, allowing opcode spaces beyond the base 0..254 range.  
     - **BlockType**: An optional integer for typed blocks (e.g., specifying return types or data types for the scope).  
     - **Condition**: If the opcode is a conditional construct (`IF`, `WHILE`), this field holds the logical comparison data.  
     - **LabelIDxs**: A list of label indices for referencing named loops, branches, or jump targets.  
     - **Variables**: An array of declared variables in scope, each describing type info, initial values, and related tokens.  
   - With these subfields, a single `Operation` node encapsulates everything needed to compile or interpret that specific piece of code in Ubytec.

5. **Extended Opcodes**  
   - Ubytec reserves the integer **255** (`OpCode = 255`) for **extended** instructions.  
   - When `OpCode` equals 255, the AST node must specify two additional fields:
     - **`ExtensionGroup`** (0..255): Identifies the category or family of extended operations.
     - **`ExtendedOpCode`** (0..255): The actual instruction code within that group.
   - **Example (extended opcode)**:
     ```json
     {
       "OpCode": 255,
       "ExtensionGroup": 16,
       "ExtendedOpCode": 17
     }
     ```
     This indicates an opcode in the extended space, group 16, instruction 17.
   - **Example (single-byte opcode)**:
     ```json
     {
       "OpCode": 12
     }
     ```
     Here, `OpCode = 12` corresponds to a standard instruction within the base 0..254 range.

6. **Condition**  
   - Represents a condition. These conditions are primarily used in branching and looping constructs (e.g., `IF`, `WHILE`).  
     - **Left**: A value or expression on the left side of the comparison.  
     - **Operand**: A comparison operator such as `==`, `!=`, `<`, `<=`, `>`, `>=`.  
     - **Right**: A value or expression on the right side of the comparison.  

7. **Variable**  
   - Contains information about a variable and its properties:
     - **BlockType**: An integer referencing the variable’s primitive or derived type.  
     - **Nullable**: A boolean that specifies whether the variable can hold a `null` value.  
     - **Name**: The identifier used to reference the variable.  
     - **Value**: An initial value or constant, if present.  
     - **SyntaxTokens**: A list of tokens pointing back to where the variable is declared in source.  
   - Commonly used inside `Operation.Variables` for scope tracking.

8. **Tokens**  
   - Each `SyntaxToken` captures how a piece of source code maps to the AST:
     - **Source**: The literal string or symbol in the code.  
     - **Line**: The entire line as it appeared in source.  
     - **Row** and **Column**: Integer positions in the file, used for precise location tracking.  
   - This mapping aids in error reporting, debugging, and tooling support, ensuring each AST node or expression can be traced to its origin in Ubytec source.

---

## Usage

1. **Validate an AST**  
   - Use a JSON Schema validator (like `ajv`, `jsonschema`, or other Draft 2020-12–compatible library).  
   - Provide this schema as reference.  
   - Ensure your AST JSON meets these structural constraints.

2. **Extend the Schema**  
   - Add new properties to `Operation` if you implement additional language features.  
   - If you add new extended opcode groups or codes, adjust the `OpCode` object fields.

3. **Compatibility**  
   - This schema follows the [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12/schema) specification.  
   - Older JSON Schema tools may need minor adaptations.

---

## Example

A minimal AST for a single block might look like:

```json
{
  "RootSentence": {
    "Nodes": [],
    "Sentences": [
      {
        "Nodes": [
          {
            "Operation": {
              "$type": "BLOCK",
              "BlockType": 0,
              "Variables": [],
              "OpCode": 2
            },
            "Children": [
              {
                "Operation": {
                  "$type": "NOP",
                  "OpCode": 1
                },
                "Children": null,
                "Tokens": [
                  {
                    "Source": "NOP",
                    "Line": "nop",
                    "Row": 1,
                    "Column": 0
                  }
                ],
                "Metadata": {
                  "guid": "0195a107-a89f-77b5-a8eb-89788871fcf9"
                }
              },
              {
                "Operation": {
                  "$type": "END",
                  "OpCode": 6
                },
                "Children": null,
                "Tokens": [
                  {
                    "Source": "END",
                    "Line": "end",
                    "Row": 2,
                    "Column": 0
                  }
                ],
                "Metadata": {
                  "guid": "0195a107-a89f-7da9-b1c4-37aec9242667"
                }
              }
            ],
            "Tokens": [
              {
                "Source": "BLOCK",
                "Line": "block t_void",
                "Row": 0,
                "Column": 0
              },
              {
                "Source": "t_void",
                "Line": "block t_void",
                "Row": 0,
                "Column": 1
              }
            ],
            "Metadata": {
              "guid": "0195a107-a89f-7a9e-99fc-8b42ae8b168a",
              "nasm": "block_0: ; BLOCK startnop   ; NOPend_block_0: ; END of block_0"
            }
          }
        ],
        "Sentences": [],
        "Metadata": {
          "guid": "0195a107-a89f-7814-bbd1-ba671479c9ef",
          "type": "block"
        }
      }
    ],
    "Metadata": {
      "guid": "0195a107-a893-7765-a43c-b51a4527bfcf",
      "type": "root"
    }
  },
  "Metadata": {
    "guid": "0195a107-a894-76cf-af8d-0ad81be9b0e4",
    "encoding": "Unicode (UTF-8)",
    "langver": "1.0.9206.40093"
  }
}
