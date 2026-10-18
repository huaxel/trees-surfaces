module IOUtils

using JSON3
using SHA

export atomic_write, atomic_write_json, file_identity, sha256_file, with_work_directory

# Content identity for provenance: a digest of the exact bytes an artifact was derived from.
# Streamed, so a multi-gigabyte input does not have to fit in memory.
sha256_file(path) = open(io -> bytes2hex(SHA.sha256(io)), path)

# Size and digest measured from one open stream, so the two can never describe different reads.
# Callers hash before and after parsing and require the results to agree, which is what makes the
# recorded digest describe the bytes that were actually analysed.
function file_identity(path)
    bytes = 0
    context = SHA.SHA256_CTX()
    open(path) do io
        buffer = Vector{UInt8}(undef, 1 << 20)
        while !eof(io)
            count = readbytes!(io, buffer)
            count == 0 && break
            bytes += count
            SHA.update!(context, view(buffer, 1:count))
        end
    end
    return (path = abspath(path), bytes = bytes, sha256 = bytes2hex(SHA.digest!(context)))
end

# Write `content` to `path` via a temporary sibling file and an atomic rename, so an
# interrupted write can never leave a truncated artifact in the destination directory.
function atomic_write(path, content::AbstractString; mode = 0o644)
    directory = dirname(abspath(path))
    mkpath(directory)
    temporary, io = mktemp(directory)
    try
        write(io, content)
        close(io)
        chmod(temporary, mode)
        mv(temporary, path; force = true)
    catch
        isopen(io) && close(io)
        rm(temporary; force = true)
        rethrow()
    end
    return path
end

atomic_write_json(path, payload) = atomic_write(path, string(JSON3.write(payload), "\n"))

# Run `f(path)` with a temporary working directory (staging or backup) for `target_dir`.
# Prefer a sibling of the target so moves and rollback renames stay on one filesystem, but fall
# back to the system temporary directory when that parent is not writable (for example a mounted
# volume root such as `/data`, where the container user cannot create siblings under `/`).
function with_work_directory(f, target_dir)
    path = try
        mktempdir(dirname(abspath(target_dir)))
    catch
        # Only directory creation is attempted here, so nothing is retried or double-executed.
        mktempdir()
    end
    try
        return f(path)
    finally
        rm(path; recursive = true, force = true)
    end
end

end
