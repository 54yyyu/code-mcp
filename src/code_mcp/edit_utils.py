"""
Code editing utilities for the Code-MCP package.

This module provides various functions for searching, replacing, and manipulating code.
"""

import re
import difflib
from pathlib import Path
from typing import List, Tuple, Optional, Union, Set, Dict, Any

class RelativeIndenter:
    """
    Rewrites text files to have relative indentation, which makes it easier 
    to search and apply edits to code blocks that differ in indentation.
    
    Adapted from Aider's RelativeIndenter.
    """
    
    def __init__(self, texts: List[str]):
        """
        Initialize the RelativeIndenter with a list of text samples.
        
        Args:
            texts: List of text strings to process
        """
        chars = set()
        for text in texts:
            chars.update(text)
        
        self.marker = "←"
        if self.marker in chars:
            self.marker = self.select_unique_marker(chars)
    
    def select_unique_marker(self, chars: Set[str]) -> str:
        """Find a Unicode character not present in the text."""
        for codepoint in range(0x10FFFF, 0x10000, -1):
            marker = chr(codepoint)
            if marker not in chars:
                return marker
        raise ValueError("Could not find a unique marker")
    
    def make_relative(self, text: str) -> str:
        """
        Transform text to use relative indents.
        
        Example:
            "    line1\n        line2\n        line3\n    line4"
        Becomes:
            "    \nline1\n    \nline2\n\nline3\n←←←←\nline4"
        """
        if self.marker in text:
            raise ValueError(f"Text already contains the outdent marker: {self.marker}")
        
        lines = text.splitlines(keepends=True)
        output = []
        prev_indent = ""
        
        for line in lines:
            line_without_end = line.rstrip("\n\r")
            len_indent = len(line_without_end) - len(line_without_end.lstrip())
            indent = line[:len_indent]
            
            change = len_indent - len(prev_indent)
            if change > 0:
                cur_indent = indent[-change:]
            elif change < 0:
                cur_indent = self.marker * -change
            else:
                cur_indent = ""
            
            out_line = cur_indent + "\n" + line[len_indent:]
            output.append(out_line)
            prev_indent = indent
        
        return "".join(output)
    
    def make_absolute(self, text: str) -> str:
        """
        Transform text from relative back to absolute indents.
        
        Reverses the transformation done by make_relative.
        """
        lines = text.splitlines(keepends=True)
        output = []
        prev_indent = ""
        
        for i in range(0, len(lines), 2):
            dent = lines[i].rstrip("\r\n")
            
            if i + 1 >= len(lines):
                break
                
            non_indent = lines[i + 1]
            
            if dent.startswith(self.marker):
                len_outdent = len(dent)
                cur_indent = prev_indent[:-len_outdent]
            else:
                cur_indent = prev_indent + dent
            
            if not non_indent.rstrip("\r\n"):
                out_line = non_indent  # don't indent a blank line
            else:
                out_line = cur_indent + non_indent
            
            output.append(out_line)
            prev_indent = cur_indent
        
        res = "".join(output)
        if self.marker in res:
            raise ValueError("Error transforming text back to absolute indents")
        
        return res


def strip_blank_lines(texts: List[str]) -> List[str]:
    """
    Strip leading and trailing blank lines from a list of text strings.
    
    Args:
        texts: List of text strings to process
        
    Returns:
        Processed list of text strings
    """
    return [text.strip("\n") + "\n" for text in texts]


def search_and_replace(texts: Tuple[str, str, str]) -> Optional[str]:
    """
    Perform a direct search and replace operation.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
        
    Returns:
        New text with replacements, or None if search_text not found
    """
    search_text, replace_text, original_text = texts
    
    if search_text not in original_text:
        return None
    
    # If search_text appears multiple times, this is still a problem
    # but we'll leave that to the caller to handle
    new_text = original_text.replace(search_text, replace_text)
    
    return new_text


def fuzzy_search_and_replace(texts: Tuple[str, str, str], threshold: float = 0.8) -> Optional[str]:
    """
    Perform a fuzzy search and replace using difflib's SequenceMatcher.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
        threshold: Similarity threshold (0.0 to 1.0)
        
    Returns:
        New text with replacements, or None if no match found
    """
    search_text, replace_text, original_text = texts
    
    # Use difflib's SequenceMatcher to find the closest match
    search_lines = search_text.splitlines()
    original_lines = original_text.splitlines()
    
    max_similarity = 0
    best_match_start = -1
    best_match_end = -1
    
    # Allow for some variance in the number of lines
    scale = 0.1
    min_len = max(1, int(len(search_lines) * (1 - scale)))
    max_len = min(len(original_lines), int(len(search_lines) * (1 + scale)))
    
    for length in range(min_len, max_len + 1):
        for i in range(len(original_lines) - length + 1):
            chunk = original_lines[i:i + length]
            chunk_text = "\n".join(chunk)
            
            similarity = difflib.SequenceMatcher(None, chunk_text, search_text).ratio()
            
            if similarity > max_similarity:
                max_similarity = similarity
                best_match_start = i
                best_match_end = i + length
    
    if max_similarity < threshold:
        return None
    
    # Replace the matched chunk with the replacement
    result_lines = (
        original_lines[:best_match_start] +
        replace_text.splitlines() +
        original_lines[best_match_end:]
    )
    
    return "\n".join(result_lines)


def replace_with_whitespace_flexibility(texts: Tuple[str, str, str]) -> Optional[str]:
    """
    Replace text with flexibility for whitespace and indentation.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
        
    Returns:
        New text with replacements, or None if no match found
    """
    search_text, replace_text, original_text = texts
    
    # Normalize whitespace in the search pattern
    normalized_search = re.sub(r'\s+', r'\\s+', re.escape(search_text))
    
    # Try to find the pattern
    matches = list(re.finditer(normalized_search, original_text))
    if not matches:
        return None
    
    # Replace the first match
    match = matches[0]
    new_text = original_text[:match.start()] + replace_text + original_text[match.end():]
    
    return new_text

def flexible_search_and_replace(
    search_text: str, 
    replace_text: str, 
    original_text: str,
    verbose: bool = False
) -> Optional[str]:
    """
    Try a series of search/replace methods, starting from the most literal
    interpretation and progressing to more flexible methods.
    
    Args:
        search_text: Text to search for
        replace_text: Text to replace with
        original_text: Original content to perform replacement in
        verbose: Whether to output detailed information about strategy selection
        
    Returns:
        New text with replacements, or None if no strategy succeeded
    """
    texts = (search_text, replace_text, original_text)
    
    # Define strategies in order of increasing flexibility
    strategies = [
        # Direct search and replace (fastest)
        search_and_replace,
        
        # Try with ellipsis handling
        try_dotdotdots,
        
        # Try with stripped blank lines
        lambda t: search_and_replace(strip_blank_lines([t[0], t[1], t[2]])),
        
        # Try with whitespace flexibility
        replace_with_whitespace_flexibility,
        
        # Try with comprehensive preprocessing (includes relative indentation)
        lambda t: apply_comprehensive_preprocessing(t),
        
        # Git-based fallback strategy (when all else fails)
        git_cherry_pick_strategy,
        
        # Last resort: fuzzy matching
        lambda t: fuzzy_search_and_replace(t, threshold=0.7),
    ]
    
    # Try each strategy until one works
    for strategy in strategies:
        try:
            if verbose:
                strategy_name = getattr(strategy, "__name__", str(strategy))
                print(f"Trying strategy: {strategy_name}")
                
            result = strategy(texts)
            if result is not None:
                if verbose:
                    strategy_name = getattr(strategy, "__name__", str(strategy))
                    print(f"Strategy succeeded: {strategy_name}")
                return result
        except Exception as e:
            # Log the error but continue to next strategy
            if verbose:
                strategy_name = getattr(strategy, "__name__", str(strategy))
                print(f"Strategy {strategy_name} failed: {str(e)}")
            continue
    
    if verbose:
        print("All strategies failed")
    
    return None


def try_dotdotdots(texts: Tuple[str, str, str]) -> Optional[str]:
    """
    Handle patterns that use "..." to indicate skipped code.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
        
    Returns:
        New text with replacements, or None if strategy doesn't apply
    """
    search_text, replace_text, original_text = texts
    
    # Check if the pattern contains "..." or "…"
    if "..." not in search_text and "…" not in search_text:
        return None
    
    # Split the text at ellipsis points
    dots_re = re.compile(r'(\.{3}|…)')
    search_pieces = dots_re.split(search_text)
    replace_pieces = dots_re.split(replace_text)
    
    # Ensure the pattern has the same number of pieces
    if len(search_pieces) != len(replace_pieces):
        return None
    
    # Skip if the pattern doesn't actually have ellipsis
    if len(search_pieces) == 1:
        return None
    
    # Create a copy of the original text to modify
    new_text = original_text
    
    # Process each piece of text between ellipses
    for i in range(0, len(search_pieces), 2):
        search_piece = search_pieces[i]
        replace_piece = replace_pieces[i]
        
        if not search_piece.strip():
            continue
        
        # Simple and fast exact replacement
        if search_piece in new_text:
            # Only replace the first occurrence to avoid multiple replacements
            new_text = new_text.replace(search_piece, replace_piece, 1)
        else:
            # Fall back to fuzzy matching for this piece
            try:
                similarity_threshold = 0.7
                best_match = None
                best_ratio = 0
                
                # Simple sliding window approach for finding best match
                pattern_len = len(search_piece)
                for j in range(len(new_text) - pattern_len + 1):
                    chunk = new_text[j:j+pattern_len]
                    ratio = difflib.SequenceMatcher(None, search_piece, chunk).ratio()
                    
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = chunk
                
                if best_ratio >= similarity_threshold and best_match:
                    new_text = new_text.replace(best_match, replace_piece, 1)
                else:
                    return None  # If any piece fails to match, the strategy fails
            except Exception:
                return None
    
    return new_text


def apply_comprehensive_preprocessing(texts: Tuple[str, str, str]) -> Optional[str]:
    """
    Apply a comprehensive set of preprocessing strategies in a logical sequence.
    This consolidates all preprocessing approaches into a single hierarchical strategy.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
        
    Returns:
        Result from the first successful preprocessing strategy, or None
    """
    # Define strategies in order of increasing complexity
    strategies = [
        # Try simple approaches first
        try_blank_line_stripping_only,
        try_whitespace_normalization,
        try_indent_alignment,
        
        # Then try combinations
        try_relative_indentation,
        try_relative_with_blank_stripping,
        try_relative_with_whitespace_norm,
        
        # Try most complex approach last
        try_all_preprocessing,
    ]
    
    for strategy in strategies:
        result = strategy(texts)
        if result:
            return result
            
    return None

def try_relative_with_whitespace_norm(texts: Tuple[str, str, str]) -> Optional[str]:
    """Apply relative indentation with whitespace normalization."""
    search_text, replace_text, original_text = texts
    
    try:
        # First normalize whitespace
        normalized_search = re.sub(r'\s+', ' ', search_text)
        normalized_replace = re.sub(r'\s+', ' ', replace_text)
        normalized_original = re.sub(r'\s+', ' ', original_text)
        
        # Then apply relative indentation
        ri = RelativeIndenter([normalized_search, normalized_replace, normalized_original])
        rel_search = ri.make_relative(normalized_search)
        rel_replace = ri.make_relative(normalized_replace)
        rel_original = ri.make_relative(normalized_original)
        
        # Try direct replacement
        if rel_search in rel_original:
            rel_result = rel_original.replace(rel_search, rel_replace)
            result = ri.make_absolute(rel_result)
            
            # Need to map this normalized result back to appropriate structure
            # This is a simplified approach - in practice you might need more careful mapping
            return result
    except ValueError:
        pass
    
    return None

def try_all_preprocessing(texts: Tuple[str, str, str]) -> Optional[str]:
    """Apply all preprocessing techniques together."""
    search_text, replace_text, original_text = texts
    
    try:
        # Strip blank lines first
        stripped_search = search_text.strip("\n") + "\n"
        stripped_replace = replace_text.strip("\n") + "\n"
        stripped_original = original_text.strip("\n") + "\n"
        
        # Then normalize whitespace (preserving line structure)
        normalized_search = "\n".join(re.sub(r'\s+', ' ', line.strip()) 
                                     for line in stripped_search.splitlines())
        normalized_replace = "\n".join(re.sub(r'\s+', ' ', line.strip()) 
                                      for line in stripped_replace.splitlines())
        normalized_original = "\n".join(re.sub(r'\s+', ' ', line.strip()) 
                                       for line in stripped_original.splitlines())
        
        # Finally apply relative indentation
        ri = RelativeIndenter([normalized_search, normalized_replace, normalized_original])
        rel_search = ri.make_relative(normalized_search)
        rel_replace = ri.make_relative(normalized_replace)
        rel_original = ri.make_relative(normalized_original)
        
        # Try direct replacement
        if rel_search in rel_original:
            rel_result = rel_original.replace(rel_search, rel_replace)
            return ri.make_absolute(rel_result)
    except ValueError:
        pass
    
    return None

def try_whitespace_normalization(texts: Tuple[str, str, str]) -> Optional[str]:
    """Try just whitespace normalization without relative indentation."""
    search_text, replace_text, original_text = texts
    
    # Normalize intra-line whitespace but preserve line breaks
    normalized_search = "\n".join(re.sub(r'\s+', ' ', line.strip()) 
                                 for line in search_text.splitlines())
    normalized_replace = "\n".join(re.sub(r'\s+', ' ', line.strip()) 
                                  for line in replace_text.splitlines())
    normalized_original = "\n".join(re.sub(r'\s+', ' ', line.strip()) 
                                   for line in original_text.splitlines())
    
    # Try direct replacement with normalized text
    if normalized_search in normalized_original:
        result = normalized_original.replace(normalized_search, normalized_replace)
        
        # Map normalized result back to original structure where possible
        # This is a simplified approach
        return result
    
    return None

def try_blank_line_stripping_only(texts: Tuple[str, str, str]) -> Optional[str]:
    """Try just stripping blank lines without other preprocessing."""
    search_text, replace_text, original_text = texts
    
    # Strip blank lines
    stripped_search = search_text.strip("\n") + "\n"
    stripped_replace = replace_text.strip("\n") + "\n"
    stripped_original = original_text.strip("\n") + "\n"
    
    # Try direct replacement with stripped text
    if stripped_search in stripped_original:
        return stripped_original.replace(stripped_search, stripped_replace)
    
    return None

def try_indent_alignment(texts: Tuple[str, str, str]) -> Optional[str]:
    """Try aligning indentation across texts without full relative indentation."""
    search_text, replace_text, original_text = texts
    
    search_lines = search_text.splitlines()
    replace_lines = replace_text.splitlines()
    original_lines = original_text.splitlines()
    
    # If any are empty, skip this strategy
    if not search_lines or not replace_lines or not original_lines:
        return None
    
    # Find minimum indentation in search text
    search_indents = [len(line) - len(line.lstrip()) for line in search_lines if line.strip()]
    if not search_indents:
        return None
    min_search_indent = min(search_indents)
    
    # Remove this common indentation from search and replace
    aligned_search_lines = []
    for line in search_lines:
        if not line.strip():
            aligned_search_lines.append(line)
        else:
            indent = len(line) - len(line.lstrip())
            if indent >= min_search_indent:
                aligned_search_lines.append(line[min_search_indent:])
            else:
                aligned_search_lines.append(line)
    
    aligned_replace_lines = []
    for line in replace_lines:
        if not line.strip():
            aligned_replace_lines.append(line)
        else:
            indent = len(line) - len(line.lstrip())
            if indent >= min_search_indent:
                aligned_replace_lines.append(line[min_search_indent:])
            else:
                aligned_replace_lines.append(line)
    
    aligned_search = "\n".join(aligned_search_lines)
    aligned_replace = "\n".join(aligned_replace_lines)
    
    # Try to find this aligned search in original
    for i in range(len(original_lines) - len(search_lines) + 1):
        # Extract potential match area
        potential_match = original_lines[i:i+len(search_lines)]
        
        # Check if indentation pattern matches
        potential_indents = [len(line) - len(line.lstrip()) for line in potential_match if line.strip()]
        if not potential_indents:
            continue
        min_potential_indent = min(potential_indents)
        
        # Align this section of original text
        aligned_potential = []
        for line in potential_match:
            if not line.strip():
                aligned_potential.append(line)
            else:
                indent = len(line) - len(line.lstrip())
                if indent >= min_potential_indent:
                    aligned_potential.append(line[min_potential_indent:])
                else:
                    aligned_potential.append(line)
        
        aligned_potential_text = "\n".join(aligned_potential)
        
        # If our aligned search matches this aligned section
        if aligned_search == aligned_potential_text:
            # Replace with adjusted indentation
            result_lines = original_lines.copy()
            for j in range(len(search_lines)):
                if i+j < len(result_lines):
                    new_line = aligned_replace_lines[j]
                    if result_lines[i+j].strip():  # If not a blank line
                        # Preserve original indentation
                        indent = len(result_lines[i+j]) - len(result_lines[i+j].lstrip())
                        new_line = " " * indent + new_line.lstrip()
                    result_lines[i+j] = new_line
            
            return "\n".join(result_lines)
    
    return None

def try_relative_indentation(texts: Tuple[str, str, str]) -> Optional[str]:
    """
    Apply the relative indentation strategy.
    This is essentially the same as the original _try_with_relative_indentation function.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
        
    Returns:
        New text with replacements applied using relative indentation, or None if failed
    """
    search_text, replace_text, original_text = texts
    
    try:
        ri = RelativeIndenter([search_text, replace_text, original_text])
        
        rel_search = ri.make_relative(search_text)
        rel_replace = ri.make_relative(replace_text)
        rel_original = ri.make_relative(original_text)
        
        # Try direct replacement with relative indentation
        if rel_search in rel_original:
            rel_result = rel_original.replace(rel_search, rel_replace)
            return ri.make_absolute(rel_result)
    except ValueError:
        pass
    
    return None

def try_relative_with_blank_stripping(texts: Tuple[str, str, str]) -> Optional[str]:
    """
    Apply relative indentation combined with blank line stripping.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
        
    Returns:
        New text with replacements applied using blank line stripping and 
        relative indentation, or None if failed
    """
    search_text, replace_text, original_text = texts
    
    try:
        # First strip blank lines
        stripped_search = search_text.strip("\n") + "\n"
        stripped_replace = replace_text.strip("\n") + "\n"
        stripped_original = original_text.strip("\n") + "\n"
        
        # Then apply relative indentation
        ri = RelativeIndenter([stripped_search, stripped_replace, stripped_original])
        rel_search = ri.make_relative(stripped_search)
        rel_replace = ri.make_relative(stripped_replace)
        rel_original = ri.make_relative(stripped_original)
        
        # Try direct replacement
        if rel_search in rel_original:
            rel_result = rel_original.replace(rel_search, rel_replace)
            result = ri.make_absolute(rel_result)
            
            # Preserve the original blank lines at start/end if possible
            leading_blanks = len(original_text) - len(original_text.lstrip("\n"))
            trailing_blanks = len(original_text) - len(original_text.rstrip("\n"))
            
            if leading_blanks > 0:
                result = "\n" * leading_blanks + result
                
            if trailing_blanks > 0:
                result = result.rstrip("\n") + "\n" * trailing_blanks
                
            return result
    except ValueError:
        pass
    
    return None

# Functions for edit block parsing

def parse_search_replace_blocks(content: str) -> List[Tuple[str, str, str]]:
    """
    Parse content containing search/replace blocks in the format:
    
    filename.py
    <<<<<<< SEARCH
    original code
    =======
    replacement code
    >>>>>>> REPLACE
    
    Args:
        content: Text content to parse
        
    Returns:
        List of tuples (filename, search_text, replace_text)
    """
    # Define regex patterns for the markers
    head_pattern = re.compile(r'<<<<<<< SEARCH\s*$', re.MULTILINE)
    divider_pattern = re.compile(r'^=======\s*$', re.MULTILINE)
    tail_pattern = re.compile(r'>>>>>>> REPLACE\s*$', re.MULTILINE)
    
    # Find all search/replace blocks
    results = []
    lines = content.splitlines()
    i = 0
    
    while i < len(lines):
        # Look for the start of a block
        if head_pattern.match(lines[i]):
            # Find the filename (should be the line before)
            filename = None
            if i > 0:
                filename = lines[i-1].strip()
            
            # Collect the search text
            search_text = []
            i += 1
            while i < len(lines) and not divider_pattern.match(lines[i]):
                search_text.append(lines[i])
                i += 1
            
            if i >= len(lines):
                # Incomplete block, skip
                break
            
            # Collect the replace text
            replace_text = []
            i += 1
            while i < len(lines) and not tail_pattern.match(lines[i]):
                replace_text.append(lines[i])
                i += 1
            
            if i >= len(lines):
                # Incomplete block, skip
                break
            
            # Convert lists to strings
            search_str = "\n".join(search_text)
            replace_str = "\n".join(replace_text)
            
            # Add to results
            if filename:
                results.append((filename, search_str, replace_str))
        
        i += 1
    
    return results


def parse_unified_diff(content: str) -> List[Tuple[str, List[str]]]:
    """
    Parse content in unified diff format.
    
    Args:
        content: Diff content to parse
        
    Returns:
        List of tuples (filename, list_of_diff_lines)
    """
    # Look for diff headers (--- file1.txt and +++ file2.txt)
    file_header_pattern = re.compile(r'^(\+\+\+ |--- )(.+)$', re.MULTILINE)
    hunk_header_pattern = re.compile(r'^@@ .+ @@.*$', re.MULTILINE)
    
    # Find all file headers
    file_matches = list(file_header_pattern.finditer(content))
    
    results = []
    
    for i in range(0, len(file_matches), 2):
        if i + 1 < len(file_matches):
            # Extract filename (from the +++ line)
            filename = file_matches[i+1].group(2).strip()
            
            # Find the start of the first hunk for this file
            hunk_start = file_matches[i+1].end()
            
            # Find the end of the diff for this file (start of next file or end of content)
            if i + 2 < len(file_matches):
                hunk_end = file_matches[i+2].start()
            else:
                hunk_end = len(content)
            
            # Extract the diff lines
            diff_content = content[hunk_start:hunk_end].strip()
            diff_lines = diff_content.splitlines()
            
            results.append((filename, diff_lines))
    
    return results


def apply_unified_diff(original_content: str, diff_lines: List[str]) -> Optional[str]:
    """
    Apply unified diff lines to original content.
    
    Args:
        original_content: Original file content
        diff_lines: Lines from a unified diff
        
    Returns:
        New content with changes applied, or None if application failed
    """
    # Create a temporary file with the original content
    original_lines = original_content.splitlines()
    result_lines = original_lines.copy()
    
    # Process each hunk
    current_line = 0
    while current_line < len(diff_lines):
        line = diff_lines[current_line]
        
        # Find hunk headers
        if line.startswith("@@"):
            # Parse the hunk header to get line numbers
            # Format: @@ -start,count +start,count @@
            header_match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if not header_match:
                current_line += 1
                continue
            
            orig_start = int(header_match.group(1)) - 1  # 0-based indexing
            
            # Collect the hunk lines
            hunk_lines = []
            current_line += 1
            
            while (current_line < len(diff_lines) and 
                   not diff_lines[current_line].startswith("@@")):
                hunk_lines.append(diff_lines[current_line])
                current_line += 1
            
            # Apply the hunk
            current_orig_line = orig_start
            line_offset = 0
            
            for hunk_line in hunk_lines:
                if hunk_line.startswith(" "):
                    # Context line - should match the original
                    if (current_orig_line < len(original_lines) and 
                        hunk_line[1:] == original_lines[current_orig_line]):
                        current_orig_line += 1
                    else:
                        # Context line doesn't match - diff can't be applied
                        return None
                
                elif hunk_line.startswith("-"):
                    # Removal line - should match the original
                    if (current_orig_line < len(original_lines) and 
                        hunk_line[1:] == original_lines[current_orig_line]):
                        # Remove this line
                        result_lines.pop(current_orig_line + line_offset)
                        line_offset -= 1
                        current_orig_line += 1
                    else:
                        # Removal line doesn't match - diff can't be applied
                        return None
                
                elif hunk_line.startswith("+"):
                    # Addition line - insert into the result
                    result_lines.insert(current_orig_line + line_offset, hunk_line[1:])
                    line_offset += 1
        else:
            current_line += 1
    
    return "\n".join(result_lines)


def process_edit_blocks(content: str, original_file_content: Dict[str, str]) -> Dict[str, str]:
    """
    Process edit blocks in the provided content and apply changes to the original files.
    
    Args:
        content: Content containing edit blocks
        original_file_content: Dict mapping filenames to their original content
        
    Returns:
        Dict mapping filenames to their updated content
    """
    updated_content = dict(original_file_content)
    
    # First, try search/replace blocks
    search_replace_blocks = parse_search_replace_blocks(content)
    for filename, search_text, replace_text in search_replace_blocks:
        if filename in original_file_content:
            file_content = original_file_content[filename]
            new_content = flexible_search_and_replace(search_text, replace_text, file_content)
            if new_content:
                updated_content[filename] = new_content
    
    # Then try unified diff format
    diff_blocks = parse_unified_diff(content)
    for filename, diff_lines in diff_blocks:
        if filename in original_file_content:
            file_content = original_file_content[filename]
            new_content = apply_unified_diff(file_content, diff_lines)
            if new_content:
                updated_content[filename] = new_content
    
    return updated_content


# Test helper function for diagnostic purposes
def generate_diff(original: str, updated: str, filename: str = "", context_lines: int = 3) -> str:
    """
    Generate a unified diff between original and updated content.
    
    Args:
        original: Original content
        updated: Updated content
        filename: Filename for the diff header
        context_lines: Number of context lines to include
        
    Returns:
        Unified diff as string
    """
    original_lines = original.splitlines()
    updated_lines = updated.splitlines()
    
    diff = difflib.unified_diff(
        original_lines,
        updated_lines,
        fromfile=f"--- {filename}",
        tofile=f"+++ {filename}",
        lineterm='',
        n=context_lines
    )
    
    return '\n'.join(diff)

def git_cherry_pick_strategy(texts):
    """
    Use git to apply patches for complex edits when other methods fail.
    
    Args:
        texts: Tuple of (search_text, replace_text, original_text)
    
    Returns:
        New text with changes applied, or None if strategy failed
    """
    try:
        import git
        from pathlib import Path
        import tempfile
        import shutil
        import os
        
        search_text, replace_text, original_text = texts
        
        # Create temporary directory with git repo
        temp_dir = tempfile.mkdtemp()
        try:
            repo = git.Repo.init(temp_dir)
            
            # Create file path
            fname = os.path.join(temp_dir, "file.txt")
            
            # Original commit
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(original_text)
            repo.git.add(str(fname))
            repo.git.commit("-m", "original")
            original_hash = repo.head.commit.hexsha
            
            # Search content commit
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(search_text)
            repo.git.add(str(fname))
            repo.git.commit("-m", "search")
            
            # Replace content commit
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(replace_text)
            repo.git.add(str(fname))
            repo.git.commit("-m", "replace")
            replace_hash = repo.head.commit.hexsha
            
            # Go back to original
            repo.git.checkout(original_hash)
            
            # Cherry pick the replace commit onto original
            try:
                repo.git.cherry_pick(replace_hash, "--minimal")
                
                # Read the new content
                with open(fname, 'r', encoding='utf-8') as f:
                    new_text = f.read()
                return new_text
            except:
                # Cherry pick failed - merge conflict or other error
                return None
        finally:
            shutil.rmtree(temp_dir)
    except:
        # Missing git or other error
        return None