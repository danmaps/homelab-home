"""Playable daily puzzles with independently checked solutions."""
import random
import math
import re
NewspaperError = ValueError


def sudoku_solutions(grid, limit=2):
    board = [[int(value) for value in row] for row in grid]
    solutions = []
    def search():
        best = None
        choices = None
        for r in range(9):
            for c in range(9):
                if board[r][c]:
                    continue
                used = set(board[r]) | {board[i][c] for i in range(9)} | {board[i][j] for i in range(r // 3 * 3, r // 3 * 3 + 3) for j in range(c // 3 * 3, c // 3 * 3 + 3)}
                possible = set(range(1, 10)) - used
                if not possible:
                    return
                if choices is None or len(possible) < len(choices):
                    best, choices = (r, c), possible
        if best is None:
            solutions.append([''.join(map(str, row)) for row in board])
            return
        r, c = best
        for value in sorted(choices):
            board[r][c] = value
            search()
            if len(solutions) >= limit:
                break
        board[r][c] = 0
    search()
    return solutions


def validate_sudoku(puzzle):
    grid, solution = puzzle.get('grid', []), puzzle.get('solution', [])
    if len(grid) != 9 or any(len(row) != 9 or any(char not in '0123456789' for char in row) for row in grid):
        raise NewspaperError('Sudoku needs nine nine-digit rows; use 0 for empty cells.')
    if len(solution) != 9 or any(len(row) != 9 or set(row) != set('123456789') for row in solution):
        raise NewspaperError('Sudoku solution rows must contain digits 1 through 9 exactly once.')
    if any({solution[r][c] for r in range(9)} != set('123456789') for c in range(9)) or any({solution[r+i][c+j] for i in range(3) for j in range(3)} != set('123456789') for r in [0,3,6] for c in [0,3,6]):
        raise NewspaperError('Sudoku solution columns or boxes are invalid.')
    if any(grid[r][c] != '0' and grid[r][c] != solution[r][c] for r in range(9) for c in range(9)):
        raise NewspaperError('Sudoku givens disagree with its solution.')
    solved = sudoku_solutions(grid)
    if solved != [solution]:
        raise NewspaperError('Sudoku must have exactly one solution matching the answer key.')
    return {'grid': grid, 'solution': solution, 'givens': sum(char != '0' for row in grid for char in row)}


def daily_sudoku(day):
    rng = random.Random('Personal Newspaper Sudoku ' + str(day))
    def shuffled(seq):
        values = list(seq); rng.shuffle(values); return values
    row_order = [band * 3 + row for band in shuffled(range(3)) for row in shuffled(range(3))]
    col_order = [stack * 3 + col for stack in shuffled(range(3)) for col in shuffled(range(3))]
    digits = shuffled('123456789')
    solution = [''.join(digits[(r * 3 + r // 3 + c) % 9] for c in col_order) for r in row_order]
    grid = [list(row) for row in solution]
    remaining = 81
    for index in shuffled(range(81)):
        if remaining <= 35:
            break
        r, c = divmod(index, 9); value = grid[r][c]; grid[r][c] = '0'
        if len(sudoku_solutions([''.join(row) for row in grid])) != 1:
            grid[r][c] = value
        else:
            remaining -= 1
    result = {'grid': [''.join(row) for row in grid], 'solution': solution, 'instructions': 'Fill each row, column and outlined 3 × 3 box with 1–9, once each.'}
    validate_sudoku(result)
    return result


def validate_chess(problem):
    import chess
    try:
        board = chess.Board(problem['fen'])
    except (KeyError, ValueError) as error:
        raise NewspaperError('Chess problem needs a valid FEN position.') from error
    if not board.is_valid() or board.is_game_over():
        raise NewspaperError('Chess problem must start from a legal, unfinished position.')
    solutions = []
    for move in board.legal_moves:
        after = board.copy(); after.push(move)
        if after.is_checkmate():
            solutions.append(move)
    if len(solutions) != 1 or problem.get('solution_uci') != solutions[0].uci():
        raise NewspaperError('Chess mate-in-one must have exactly one legal solution matching its key.')
    move = solutions[0]
    san = board.san(move)
    if problem.get('solution_san', san) != san:
        raise NewspaperError('Chess answer notation does not match the checked move.')
    rows = [[board.piece_at(chess.square(file, rank)).unicode_symbol() if board.piece_at(chess.square(file, rank)) else '' for file in range(8)] for rank in range(7, -1, -1)]
    return {'rows': rows, 'side': 'White' if board.turn else 'Black', 'san': san, 'fen': board.fen()}


def daily_chess(day):
    import chess
    rng = random.Random('Personal Newspaper Chess ' + str(day))
    edges = [sq for sq in chess.SQUARES if chess.square_file(sq) in {0, 7} or chess.square_rank(sq) in {0, 7}]
    for _ in range(4000):
        board = chess.Board(None)
        black_king = rng.choice(edges)
        white_king = rng.choice([sq for sq in chess.SQUARES if chess.square_distance(sq, black_king) in {2, 3}])
        queen = rng.choice([sq for sq in chess.SQUARES if sq not in {white_king, black_king}])
        board.set_piece_at(black_king, chess.Piece(chess.KING, chess.BLACK))
        board.set_piece_at(white_king, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(queen, chess.Piece(chess.QUEEN, chess.WHITE))
        if not board.is_valid() or board.is_game_over():
            continue
        mates = []
        for move in board.legal_moves:
            after = board.copy(); after.push(move)
            if after.is_checkmate():
                mates.append(move)
        if len(mates) == 1:
            result = {'fen': board.fen(), 'solution_uci': mates[0].uci(), 'solution_san': board.san(mates[0]),
                      'instructions': 'White to move. Find the only move that gives immediate checkmate.',
                      'explanation': 'The queen checks the king while the white king and queen cover every escape square. The checking queen cannot be captured legally.'}
            validate_chess(result)
            return result
    raise NewspaperError('Could not construct a verified unique chess problem.')


def validate_crossword(puzzle, personalized_ratio=0.5):
    grid = puzzle.get("grid", [])
    if len(grid) != 5 or any(len(row) != 5 or not re.fullmatch(r"[A-Z#]{5}", row) for row in grid):
        raise NewspaperError("Crossword must be a 5 by 5 A-Z/# grid.")
    answers = []
    labels = {}
    number = 0
    for r in range(5):
        for c in range(5):
            if grid[r][c] == "#":
                continue
            across = (c == 0 or grid[r][c - 1] == "#") and c + 1 < 5 and grid[r][c + 1] != "#"
            down = (r == 0 or grid[r - 1][c] == "#") and r + 1 < 5 and grid[r + 1][c] != "#"
            if across or down:
                number += 1
                labels[f"{r},{c}"] = number
            for direction, is_start in [("across", across), ("down", down)]:
                if not is_start:
                    continue
                rr, cc = r, c
                answer = ""
                while rr < 5 and cc < 5 and grid[rr][cc] != "#":
                    answer += grid[rr][cc]
                    rr += direction == "down"
                    cc += direction == "across"
                if len(answer) < 3:
                    raise NewspaperError("Every crossword entry must have at least three letters.")
                answers.append((direction, number, answer))
    # Every white cell participates in an across and down run of at least three.
    for r in range(5):
        for c in range(5):
            if grid[r][c] == "#":
                continue
            left = right = c
            top = bottom = r
            while left > 0 and grid[r][left - 1] != "#": left -= 1
            while right < 4 and grid[r][right + 1] != "#": right += 1
            while top > 0 and grid[top - 1][c] != "#": top -= 1
            while bottom < 4 and grid[bottom + 1][c] != "#": bottom += 1
            if right - left + 1 < 3 or bottom - top + 1 < 3:
                raise NewspaperError("Crossword contains an unchecked or short white run.")
    if not answers:
        raise NewspaperError("A crossword needs white cells and playable answers.")
    clues = puzzle.get("clues", [])
    actual = {(x["direction"], x["number"], x["answer"]) for x in clues}
    if actual != set(answers) or len(clues) != len(answers):
        raise NewspaperError("Crossword clues, answers, numbering, and grid disagree.")
    if any(not x.get("clue", "").strip() for x in clues):
        raise NewspaperError("Every crossword answer requires a clue.")
    personalized = [x for x in clues if x.get("personalized") and x.get("personal_context")]
    if not 0 <= personalized_ratio <= 1:
        raise NewspaperError("Personalized clue ratio must be between zero and one.")
    if len(personalized) < math.ceil(len(clues) * personalized_ratio):
        raise NewspaperError("The configured fraction of crossword clues must have documented personal context.")
    return {"labels": labels, "answers": answers, "personalized": len(personalized)}

def validate_jumble(puzzle):
    from collections import Counter
    words = puzzle.get("words", [])
    if len(words) != 4:
        raise NewspaperError("Jumble needs exactly four words.")
    extracted = ""
    for word in words:
        answer, scrambled = word.get("answer", ""), word.get("scrambled", "")
        if not re.fullmatch(r"[A-Z]{3,12}", answer) or Counter(answer) != Counter(scrambled) or answer == scrambled:
            raise NewspaperError("Invalid Jumble letters or unchanged scramble.")
        positions = word.get("circles", [])
        if len(set(positions)) != len(positions) or any(not isinstance(i, int) or i < 0 or i >= len(answer) for i in positions):
            raise NewspaperError("Invalid Jumble circle positions.")
        extracted += "".join(answer[i] for i in positions)
    bonus = re.sub(r"[^A-Z]", "", puzzle.get("bonus", "").upper())
    if not bonus or Counter(extracted) != Counter(bonus) or not puzzle.get("bonus_clue"):
        raise NewspaperError("Jumble bonus does not match circled solution letters.")
    return True
